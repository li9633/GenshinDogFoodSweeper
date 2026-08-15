"""
圣遗物扫描 Presenter
====================
将鼠标操作暴露给 QML 调试面板，用于测试圣遗物定位、点击与精准翻页功能。

本 Presenter 仅负责：
- QML 属性/信号/Slot 的声明与暴露
- UI 状态管理
- OCR 任务调度（调 OcrWorker）
- 调试预览图生成（调 SliderDetector）
- 将具体操作委托给 automation 层模块

纯逻辑层已提取到：
- backend.automation.slider_detector  → 滑块颜色检测
- backend.automation.anchor_locator   → 锚点定位、空格子检测
- backend.automation.artifact_scanner → 扫描 Worker 线程
"""

from __future__ import annotations

from pathlib import Path
from time import sleep

import cv2
import numpy as np
from models.artifact import ArtifactInfo
from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot
from utils.logger import log

from backend.automation.anchor_locator import AnchorLocator
from backend.automation.artifact_count_ocr import ocr_artifact_count
from backend.automation.artifact_scanner import (
    BatchClickWorker,
    FullScanWorker,
    SmartScrollToBottomWorker,
)
from backend.automation.debug_preview import DebugPreview
from backend.automation.grid_click_config import GridClickConfig
from backend.automation.mouse_controller import MouseController
from backend.automation.ocr_engine import OcrEngine
from backend.automation.page_scroller import PageScroller
from backend.automation.roi_config import ANCHOR_ROI_DEFINITIONS
from backend.automation.slider_detector import SliderDetector
from backend.automation.slider_scroller import SliderScroller
from backend.automation.slot_detector import SlotDetector
from backend.automation.window_helper import WindowHelper
from backend.utils.screen_capture import ScreenshotCapture

from .image_provider import PreviewImageProvider


class ArtifactScanPresenter(QObject):
    """圣遗物扫描 — 注册为 QML context property

    QML 传入的坐标是相对于原神窗口左上角的偏移，
    内部自动转换为屏幕绝对坐标后调用 MouseController。
    """

    # ========== 信号 ==========

    batchProgressChanged = Signal()
    batchRunningChanged = Signal()
    # 首尾锚点定位
    anchorFirstMarked = Signal()
    anchorLastFound = Signal()
    anchorPagesCalculated = Signal()
    anchorScrollRunningChanged = Signal()
    scrollbarDragFinished = Signal()
    scrollbarTrackHeightChanged = Signal()
    debugPreviewReady = Signal(str)

    # 锚点识别结果
    anchorFirstRecognizedChanged = Signal()
    anchorTailRecognizedChanged = Signal()

    # 全量扫描
    fullScanStepChanged = Signal()
    fullScanProgressChanged = Signal()
    fullScanPageChanged = Signal()
    fullScanRunningChanged = Signal()
    fullScanFinished = Signal()
    fullScanArtifactScanned = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._mouse = MouseController()
        self._capture = ScreenshotCapture()
        self._win_helper = WindowHelper(self._capture, self._mouse)
        self._slider_scroller = SliderScroller(
            self._mouse, self._capture, self._win_helper,
            debug_callback=self._emit_slider_debug,
        )

        # 批量点击
        self._batch_progress = ""
        self._batch_running = False
        self._batch_worker: BatchClickWorker | None = None

        self._page_scroller = PageScroller(self._mouse, self._capture)

        # 首尾锚点
        self._anchor_first_x = 0
        self._anchor_first_y = 0
        self._anchor_first_w = 0
        self._anchor_first_h = 0
        self._anchor_last_x = 0
        self._anchor_last_y = 0
        self._anchor_tail_x = 0
        self._anchor_tail_y = 0
        self._anchor_tail_info: ArtifactInfo | None = None
        self._anchor_total_pages = 0
        self._anchor_total_rows = 0
        self._anchor_scroll_running = False
        self._anchor_first_template: np.ndarray | None = None
        self._grid_gap = 24

        # 智能滚轮到底
        self._scroll_to_bottom_worker: SmartScrollToBottomWorker | None = None
        self._scrollbar_track_height = 760

        # 锚点OCR识别
        self._anchor_ocr_connected = False
        self._anchor_first_display_text = ""
        self._anchor_tail_display_text = ""
        self._anchor_first_recognized = False
        self._anchor_tail_recognized = False

        # 全量扫描
        self._full_scan_worker: FullScanWorker | None = None
        self._full_scan_step = ""
        self._full_scan_progress = ""
        self._full_scan_running = False
        self._full_scan_current_page = 0
        self._full_scan_total_pages = 0
        self._full_scan_results: list[ArtifactInfo] = []

    # ==================================================================
    # 内部工具
    # ==================================================================

    def _window_origin(self) -> tuple[int, int]:
        return self._win_helper.get_origin()

    def _genshin_hwnd(self) -> int | None:
        return self._win_helper.get_hwnd()

    def _to_absolute(self, x: int, y: int) -> tuple[int, int]:
        return self._win_helper.to_absolute(x, y)

    # ==================================================================
    # 基础鼠标操作
    # ==================================================================

    @Slot(int, int)
    def moveTo(self, x: int, y: int) -> None:
        ax, ay = self._to_absolute(x, y)
        ok = self._mouse.move_to(ax, ay)
        log.info(
            f"鼠标移动: 窗口({x}, {y}) → 屏幕({ax}, {ay}) {'成功' if ok else '失败'}"
        )

    @Slot(int, int)
    def clickAt(self, x: int, y: int) -> None:
        ax, ay = self._to_absolute(x, y)
        ok = self._mouse.move_and_click(ax, ay)
        log.debug(
            f"鼠标点击: 窗口({x}, {y}) → 屏幕({ax}, {ay}) {'成功' if ok else '失败'}"
        )

    @Slot()
    def focusGame(self) -> None:
        self._win_helper.focus()

    @Slot(int, int)
    def moveAndClick(self, x: int, y: int) -> None:
        self.clickAt(x, y)

    @Slot(int)
    def scrollWheel(self, clicks: int) -> None:
        ok = self._mouse.scroll(clicks)
        log.info(f"滚轮: {clicks} {'成功' if ok else '失败'}")

    # ==================================================================
    # 批量点击
    # ==================================================================

    @Property(str, notify=batchProgressChanged)
    def batchProgress(self) -> str:
        return self._batch_progress

    @Property(bool, notify=batchRunningChanged)
    def batchRunning(self) -> bool:
        return self._batch_running

    @Slot(int, int, int, int, int, int, int, int)
    def startBatchClick(
        self,
        margin_x: int,
        margin_y: int,
        item_w: int,
        item_h: int,
        gap: int,
        rows: int,
        cols: int,
        interval_ms: int,
    ) -> None:
        if self._batch_running:
            return
        ox, oy = self._window_origin()
        if ox == 0 and oy == 0:
            log.warning("未检测到原神窗口")
            return

        self._batch_worker = BatchClickWorker(
            mouse=self._mouse,
            config=GridClickConfig(
                origin_x=ox,
                origin_y=oy,
                margin_x=margin_x,
                margin_y=margin_y,
                item_w=item_w,
                item_h=item_h,
                gap=gap,
                rows=rows,
                cols=cols,
                interval_ms=interval_ms,
                auto_focus=True,
            ),
            win=self._win_helper,
        )
        self._batch_worker.progress.connect(self._on_batch_progress)
        self._batch_worker.finished.connect(self._on_batch_finished)

        self._batch_running = True
        self._batch_progress = "0/" + str(rows * cols)
        self.batchRunningChanged.emit()
        self.batchProgressChanged.emit()
        self._batch_worker.start()
        log.info(f"批量点击开始: {rows}×{cols} 网格, 间隔={interval_ms}ms")

    @Slot()
    def stopBatchClick(self) -> None:
        if self._batch_worker is not None:
            self._batch_worker.stop()
        log.info("批量点击已停止")

    def _on_batch_progress(self, current: int, total: int) -> None:
        self._batch_progress = f"{current}/{total}"
        self.batchProgressChanged.emit()

    def _on_batch_finished(self) -> None:
        self._batch_running = False
        self._batch_worker = None
        self.batchRunningChanged.emit()
        log.info("批量点击完成")

    # ==================================================================
    # 基于格子检测的精准翻页
    # ==================================================================

    @Slot(int, int, int)
    def scrollPageByDetection(
        self, flag_x: int, flag_y: int, scroll_delay_ms: int = 80
    ) -> None:
        """格子翻页：截图 → 检测 → 计算 → 滚动，全部委托 PageScroller。"""
        self.focusGame()
        ox, oy = self._window_origin()
        if ox == 0 and oy == 0:
            log.warning("未检测到原神窗口")
            return
        self._page_scroller.scroll_to_next_page(
            ox, oy, flag_x, flag_y,
            tick_delay_ms=scroll_delay_ms,
        )
        log.info("格子翻页完成")

    @Slot(int, int, int)
    def scrollPageToBottom(
        self, flag_x: int, flag_y: int, scroll_delay_ms: int = 80
    ) -> None:
        """自动翻到底：OCR 识别数量 → 计算总页数 → 循环 截图→检测→滚动。"""
        self.focusGame()
        ox, oy = self._window_origin()
        if ox == 0 and oy == 0:
            log.warning("未检测到原神窗口")
            return

        # OCR 识别圣遗物数量，计算总页数
        engines_dir = Path(__file__).resolve().parents[3] / "engines"
        ocr = OcrEngine._create_paddle_ocr(engines_dir)
        count = ocr_artifact_count(self._capture, ocr)
        total_pages = max(1, (count + 31) // 32) if count > 0 else 0
        max_pages = total_pages - 1 if total_pages > 0 else 0
        log.info(
            f"自动翻到底开始... 圣遗物数量={count}, 总页数={total_pages}, 安全上限={max_pages}"
        )
        pages = self._page_scroller.scroll_to_bottom(
            ox, oy, flag_x, flag_y,
            tick_delay_ms=scroll_delay_ms,
            max_pages=max_pages,
            total_pages=total_pages,
        )
        log.info(f"自动翻到底完成: 共翻页 {pages} 次")

    # ==================================================================
    # 首尾锚点定位
    # ==================================================================

    @Property(int, notify=anchorFirstMarked)
    def anchorFirstX(self) -> int:
        return self._anchor_first_x

    @Property(int, notify=anchorFirstMarked)
    def anchorFirstY(self) -> int:
        return self._anchor_first_y

    @Property(int, notify=anchorFirstMarked)
    def anchorFirstW(self) -> int:
        return self._anchor_first_w

    @Property(int, notify=anchorFirstMarked)
    def anchorFirstH(self) -> int:
        return self._anchor_first_h

    @Property(int, notify=anchorLastFound)
    def anchorLastX(self) -> int:
        return self._anchor_last_x

    @Property(int, notify=anchorLastFound)
    def anchorLastY(self) -> int:
        return self._anchor_last_y

    @Property(int, notify=anchorPagesCalculated)
    def anchorTotalPages(self) -> int:
        return self._anchor_total_pages

    @Property(int, notify=anchorPagesCalculated)
    def anchorTotalRows(self) -> int:
        return self._anchor_total_rows

    @Property(bool, notify=anchorScrollRunningChanged)
    def anchorScrollRunning(self) -> bool:
        return self._anchor_scroll_running

    @Property(str, notify=anchorFirstRecognizedChanged)
    def anchorFirstDisplayText(self) -> str:
        return self._anchor_first_display_text

    @Property(str, notify=anchorTailRecognizedChanged)
    def anchorTailDisplayText(self) -> str:
        return self._anchor_tail_display_text

    @Property(bool, notify=anchorFirstRecognizedChanged)
    def anchorFirstRecognized(self) -> bool:
        return self._anchor_first_recognized

    @Property(bool, notify=anchorTailRecognizedChanged)
    def anchorTailRecognized(self) -> bool:
        return self._anchor_tail_recognized

    @Slot(int, int, int, int)
    def recognizeFirstAnchor(self, x: int, y: int, w: int, h: int) -> None:
        """识别首锚点：标记位置 → 点击物品 → OCR识别圣遗物信息"""
        self._anchor_first_x = x
        self._anchor_first_y = y
        self._anchor_first_w = w
        self._anchor_first_h = h
        self._anchor_last_x = 0
        self._anchor_last_y = 0
        self._anchor_tail_x = 0
        self._anchor_tail_y = 0
        self._anchor_tail_info = None
        self._anchor_total_pages = 0
        self._anchor_total_rows = 0
        self._anchor_first_display_text = ""
        self._anchor_first_recognized = False
        self.anchorFirstMarked.emit()
        self.anchorLastFound.emit()
        self.anchorPagesCalculated.emit()
        self.anchorFirstRecognizedChanged.emit()
        log.info(f"首锚点已标记: ({x}, {y}, {w}x{h}), 开始OCR识别...")
        self._recognize_anchor_item(x + w // 2, y + h // 2, "first")

    @Slot()
    def findLastAnchor(self) -> None:
        """模板匹配查找最后一个圣遗物（尾锚点）"""
        if self._anchor_first_template is None:
            log.warning("请先标记首锚点")
            return
        result = self._capture.capture()
        if result is None:
            log.warning("截图失败")
            return
        from backend.automation.template_matcher import find_all_matches

        screen_gray = cv2.cvtColor(result.image, cv2.COLOR_RGB2GRAY)
        matches = find_all_matches(
            screen_gray, self._anchor_first_template, threshold=0.7
        )
        if not matches:
            self.anchorLastFound.emit()
            log.info("尾锚点查找: 模板匹配未找到结果")
            return
        best = matches[-1]
        score, x, y, _w, _h = best
        self._anchor_last_x = x
        self._anchor_last_y = y
        self.anchorLastFound.emit()
        log.info(
            f"尾锚点已找到: ({x}, {y}) 置信度={score:.2f}, "
            f"共匹配到 {len(matches)} 个位置"
        )
        self._calculate_anchor_pages()

    @Slot(int, int)
    def markLastAnchor(self, x: int, y: int) -> None:
        """手动标记尾锚点"""
        self._anchor_last_x = x
        self._anchor_last_y = y
        self.anchorLastFound.emit()
        log.info(f"尾锚点已手动标记: ({x}, {y})")
        self._calculate_anchor_pages()

    def _calculate_anchor_pages(self) -> None:
        """根据首尾锚点计算总页数 — 委托给 AnchorLocator"""
        if self._anchor_first_y == 0 or self._anchor_last_y == 0:
            return
        is_tail_center = self._anchor_tail_y != 0
        rows, pages = AnchorLocator.calculate_pages(
            self._anchor_first_y,
            self._anchor_last_y,
            self._anchor_first_h,
            self._grid_gap,
            is_tail_center=is_tail_center,
        )
        self._anchor_total_rows = rows
        self._anchor_total_pages = pages
        self.anchorPagesCalculated.emit()
        log.info(
            f"锚点计算: first=({self._anchor_first_x},{self._anchor_first_y}) "
            f"last=({self._anchor_last_x},{self._anchor_last_y}) "
            f"→ {rows} 行, {pages} 页"
        )

    @Slot()
    def recognizeLastAnchor(self) -> None:
        """识别尾锚点：点击已定位的尾锚点物品 → OCR识别圣遗物信息"""
        tail_x = self._anchor_tail_x or self._anchor_last_x
        tail_y = self._anchor_tail_y or self._anchor_last_y
        if tail_x == 0 and tail_y == 0:
            log.warning("尾锚点识别: 尚未定位尾锚点，请先执行智能拖拽到底")
            return
        self._anchor_tail_display_text = ""
        self._anchor_tail_recognized = False
        self.anchorTailRecognizedChanged.emit()
        log.info(f"尾锚点识别: 点击({tail_x}, {tail_y})，开始OCR识别...")
        self._recognize_anchor_item(tail_x, tail_y, "tail")

    # ==================================================================
    # 锚点 OCR 识别
    # ==================================================================

    def _connect_anchor_ocr_worker(self) -> None:
        if self._anchor_ocr_connected:
            return
        from backend.automation.ocr_worker import OcrWorker

        worker = OcrWorker.instance()
        worker.task_done.connect(self._on_anchor_ocr_done)
        worker.task_error.connect(self._on_anchor_ocr_error)
        self._anchor_ocr_connected = True

    def _recognize_anchor_item(
        self, cx: int, cy: int, anchor_type: str,
    ) -> None:
        """点击锚点物品 → 延迟等待详情面板 → 截图 → 提交OCR任务"""
        self._connect_anchor_ocr_worker()
        self.focusGame()
        ax, ay = self._to_absolute(cx, cy)
        self._mouse.move_and_click(ax, ay)

        def _capture_and_ocr() -> None:
            result = self._capture.capture()
            if result is None:
                log.warning(f"锚点识别({anchor_type}): 截图失败")
                return
            roi_configs = {
                name: (dx, dy, dw, dh)
                for name, dx, dy, dw, dh in ANCHOR_ROI_DEFINITIONS
            }
            task = self._create_anchor_ocr_task(
                result.image, roi_configs, anchor_type,
            )
            from backend.automation.ocr_worker import OcrWorker

            OcrWorker.instance().submit(task, callback_data=anchor_type)

        QTimer.singleShot(200, _capture_and_ocr)

    @staticmethod
    def _create_anchor_ocr_task(image, roi_configs, anchor_type):
        def task(ocr) -> dict:
            from backend.automation.recognizer import ArtifactRecognizer
            from backend.ui.presenters.artifact_recognition_presenter import (
                ArtifactRecognitionPresenter,
            )

            artifact = ArtifactRecognizer.recognize(image, roi_configs, ocr)
            display_lines = AnchorLocator.format_artifact_display(artifact)
            structured_lines = (
                ArtifactRecognitionPresenter._format_structured(artifact)
            )
            return {
                "anchor_type": anchor_type,
                "artifact": artifact,
                "display_lines": display_lines,
                "structured_lines": structured_lines,
            }
        return task

    def _on_anchor_ocr_done(
        self, result: dict, callback_data: object,
    ) -> None:
        if not isinstance(result, dict) or "anchor_type" not in result:
            return
        anchor_type = result["anchor_type"]
        display_text = "\n".join(result.get("display_lines", []))
        if anchor_type == "first":
            self._anchor_first_display_text = display_text
            self._anchor_first_recognized = True
            self.anchorFirstRecognizedChanged.emit()
            log.info(f"首锚点识别完成:\n{display_text}")
        elif anchor_type == "tail":
            self._anchor_tail_display_text = display_text
            self._anchor_tail_recognized = True
            self.anchorTailRecognizedChanged.emit()
            log.info(f"尾锚点识别完成:\n{display_text}")

    def _on_anchor_ocr_error(
        self, error: str, callback_data: object,
    ) -> None:
        log.error(f"锚点OCR识别失败({callback_data}): {error}")

    # ==================================================================
    # 全量扫描
    # ==================================================================

    @Property(str, notify=fullScanStepChanged)
    def fullScanStep(self) -> str:
        return self._full_scan_step

    @Property(str, notify=fullScanProgressChanged)
    def fullScanProgress(self) -> str:
        return self._full_scan_progress

    @Property(bool, notify=fullScanRunningChanged)
    def fullScanRunning(self) -> bool:
        return self._full_scan_running

    @Property(int, notify=fullScanPageChanged)
    def fullScanCurrentPage(self) -> int:
        return self._full_scan_current_page

    @Property(int, notify=fullScanPageChanged)
    def fullScanTotalPages(self) -> int:
        return self._full_scan_total_pages

    @Slot(int, int, int, int, int, int, int, int, int, int, int, int, int, int, int)
    def startFullScan(
        self,
        margin_x: int,
        margin_y: int,
        item_w: int,
        item_h: int,
        gap: int,
        slider_region_x: int,
        slider_top_y: int,
        slider_bottom_y: int,
        slider_region_w: int,
        slider_region_h: int,
        scroll_flag_x: int,
        scroll_flag_y: int,
        tick_delay_ms: int,
        page_settle_ms: int,
        click_interval_ms: int,
    ) -> None:
        """开始全量圣遗物扫描 — 委托给 FullScanWorker"""
        if self._full_scan_running:
            log.warning("全量扫描已在运行中")
            return
        ox, oy = self._window_origin()
        if ox == 0 and oy == 0:
            log.warning("未检测到原神窗口")
            return

        roi_configs = {
            name: (dx, dy, dw, dh)
            for name, dx, dy, dw, dh in ANCHOR_ROI_DEFINITIONS
        }
        engines_dir = Path(__file__).resolve().parents[3] / "engines"

        self._full_scan_results = []
        self._full_scan_worker = FullScanWorker(
            mouse=self._mouse,
            capture=self._capture,
            engines_dir=engines_dir,
            margin_x=margin_x,
            margin_y=margin_y,
            item_w=item_w,
            item_h=item_h,
            gap=gap,
            roi_configs=roi_configs,
            anchor_first_x=self._anchor_first_x or 118,
            anchor_first_y=self._anchor_first_y or 189,
            anchor_first_w=self._anchor_first_w or item_w,
            anchor_first_h=self._anchor_first_h or item_h,
            slider_region_x=slider_region_x,
            slider_top_y=slider_top_y,
            slider_bottom_y=slider_bottom_y,
            slider_region_w=slider_region_w,
            slider_region_h=slider_region_h,
            scroll_flag_x=scroll_flag_x,
            scroll_flag_y=scroll_flag_y,
            tick_delay_ms=tick_delay_ms,
            page_settle_ms=page_settle_ms,
            click_interval_ms=click_interval_ms,
        )
        self._full_scan_worker.stepChanged.connect(self._on_full_scan_step)
        self._full_scan_worker.progressChanged.connect(self._on_full_scan_progress)
        self._full_scan_worker.pageChanged.connect(self._on_full_scan_page)
        self._full_scan_worker.artifactScanned.connect(self._on_full_scan_artifact)
        self._full_scan_worker.finished.connect(self._on_full_scan_finished)
        self._full_scan_worker.errorOccurred.connect(self._on_full_scan_error)

        self._full_scan_running = True
        self._full_scan_step = "正在初始化..."
        self._full_scan_progress = ""
        self._full_scan_current_page = 0
        self._full_scan_total_pages = 0
        self.fullScanRunningChanged.emit()
        self.fullScanStepChanged.emit()
        self._full_scan_worker.start()
        log.info("全量扫描开始")

    @Slot()
    def stopFullScan(self) -> None:
        if self._full_scan_worker is not None:
            self._full_scan_worker.stop()
        log.info("全量扫描已请求停止")

    def _on_full_scan_step(self, step: str) -> None:
        self._full_scan_step = step
        self.fullScanStepChanged.emit()

    def _on_full_scan_progress(self, current: int, total: int) -> None:
        self._full_scan_progress = f"{current}/{total}"
        self.fullScanProgressChanged.emit()

    def _on_full_scan_page(self, current: int, total: int) -> None:
        self._full_scan_current_page = current
        self._full_scan_total_pages = total
        self.fullScanPageChanged.emit()

    def _on_full_scan_artifact(self, _display: str, _is_material: bool) -> None:
        self.fullScanArtifactScanned.emit()

    def _on_full_scan_finished(self, scanned: int, expected: int) -> None:
        self._full_scan_running = False
        self._full_scan_worker = None
        self._full_scan_step = f"扫描完成: 背包{expected}个, 识别{scanned}个"
        self._full_scan_progress = f"{scanned}/{expected}"
        self.fullScanRunningChanged.emit()
        self.fullScanStepChanged.emit()
        self.fullScanProgressChanged.emit()
        self.fullScanFinished.emit()
        log.info(f"全量扫描完成: 背包{expected}个, 识别{scanned}个")

    def _on_full_scan_error(self, error: str) -> None:
        self._full_scan_running = False
        self._full_scan_worker = None
        self._full_scan_step = f"扫描出错: {error[:100]}"
        self.fullScanRunningChanged.emit()
        self.fullScanStepChanged.emit()
        log.error(f"全量扫描出错: {error}")

    # ==================================================================
    # 滚动条拖拽到底
    # ==================================================================

    @Property(int, notify=scrollbarTrackHeightChanged)
    def scrollbarTrackHeight(self) -> int:
        return self._scrollbar_track_height

    @scrollbarTrackHeight.setter
    def scrollbarTrackHeight(self, value: int) -> None:
        if self._scrollbar_track_height != value:
            self._scrollbar_track_height = value
            self.scrollbarTrackHeightChanged.emit()

    @Slot(int, int, int, int, int, int, int)
    def scrollToBottom(
        self,
        region_x: int,
        bottom_y: int,
        bottom_w: int,
        bottom_h: int,
        top_y: int,
        top_w: int,
        top_h: int,
    ) -> None:
        """智能拖拽到底：检测顶部 → 拖拽 → 检测底部 → 完成"""
        if (
            self._scroll_to_bottom_worker is not None
            and self._scroll_to_bottom_worker.isRunning()
        ):
            return

        ox, oy = self._window_origin()
        if ox == 0 and oy == 0:
            log.warning("未检测到原神窗口")
            return

        result = self._capture.capture()
        if result is None:
            log.warning("截图失败")
            return

        # Step 1: 确保滑块在顶部
        slider_y = self._slider_scroller.ensure_at_top(
            region_x, top_y, bottom_y, bottom_w, bottom_h
        )
        if slider_y is None:
            return

        window = self._capture.find_genshin_window()
        window_bottom = (oy + window.height) if window else (oy + 1000)

        self._scroll_to_bottom_worker = SmartScrollToBottomWorker(
            mouse=self._mouse,
            capture=self._capture,
            ox=ox,
            oy=oy,
            region_x=region_x,
            region_y=bottom_y,
            region_w=bottom_w,
            region_h=bottom_h,
            initial_slider_y=slider_y,
            window_bottom=window_bottom,
        )
        self._scroll_to_bottom_worker.progress.connect(
            self._onScrollToBottomProgress
        )
        self._scroll_to_bottom_worker.final_slider_y.connect(
            self._on_smart_scroll_final_slider_y
        )
        self._scroll_to_bottom_worker.finished.connect(
            self._onScrollToBottomFinished
        )
        self._scroll_to_bottom_worker.start()
        self._anchor_scroll_running = True
        self.anchorScrollRunningChanged.emit()

    @Slot(int)
    def _on_smart_scroll_final_slider_y(self, slider_y: int) -> None:
        """智能拖拽完成后，根据格子检测定位尾锚点（最后一页最后一个物品）"""
        result = self._capture.capture()
        if result is None:
            log.warning("尾锚点定位: 截图失败")
            return
        slots = SlotDetector.detect(result.image, roi=PageScroller._ROI)
        if not slots:
            log.warning("尾锚点定位: 未检测到格子")
            return
        # slots 按 y 再 x 排序，最后一个即为右下角尾锚点
        last_slot = slots[-1]
        tail_cx, tail_cy = last_slot[0], last_slot[1]
        log.info(f"尾锚点定位: 格子检测 → 最后一个格子 ({tail_cx}, {tail_cy})")
        self._anchor_tail_x, self._anchor_tail_y = tail_cx, tail_cy
        self._anchor_last_x = tail_cx
        self._anchor_last_y = tail_cy
        self.anchorLastFound.emit()
        self._calculate_anchor_pages()

    def _onScrollToBottomProgress(self, count: int) -> None:
        log.info(f"智能拖拽到底: 已拖拽 {count} 次")

    def _onScrollToBottomFinished(self) -> None:
        self._anchor_scroll_running = False
        self.anchorScrollRunningChanged.emit()
        log.info("智能拖拽到底完成")
        self.scrollbarDragFinished.emit()

    # ==================================================================
    # 颜色检测到底（滑块检测委托给 SliderDetector）
    # ==================================================================

    @Slot(int, int, int, int)
    def checkScrollBottomByColor(
        self, region_x: int, region_y: int, region_w: int, region_h: int
    ) -> None:
        """颜色检测是否到底 — 委托 SliderScroller"""
        slider_y, is_at_bottom = self._slider_scroller.check_bottom_by_color(
            region_x, region_y, region_w, region_h
        )
        if slider_y is None:
            return
        if is_at_bottom:
            log.info(f"追加{SliderDetector.EXTRA_TICKS}次滚动确保100%到底")
            ox, oy = self._window_origin()
            if ox != 0 or oy != 0:
                abs_x = ox + region_x + region_w // 2
                abs_y = oy + region_y + region_h // 2
                self._mouse.move_to(abs_x, abs_y)
                for _ in range(SliderDetector.EXTRA_TICKS):
                    self._mouse.scroll_one_tick()
                    sleep(0.03)
            log.info("颜色检测: 已确认到底，追加滚动完成")

    def _scroll_verify_bottom(
        self,
        region_x: int,
        region_y: int,
        region_w: int,
        region_h: int,
        initial_slider_y: int,
    ) -> int | None:
        return self._slider_scroller.verify_bottom(
            region_x, region_y, region_w, region_h, initial_slider_y
        )

    def _scroll_verify_top(
        self,
        region_x: int,
        top_y: int,
        bottom_y: int,
        region_w: int,
        region_h: int,
        initial_slider_y: int,
    ) -> int | None:
        return self._slider_scroller.verify_top(
            region_x, top_y, bottom_y, region_w, region_h, initial_slider_y
        )

    # ==================================================================
    # 调试预览
    # ==================================================================

    def _emit_slider_debug(
        self,
        img: np.ndarray,
        region_x: int,
        top_y: int,
        bottom_y: int,
        region_w: int,
        region_h: int,
        slider_y: int | None,
        label: str = "",
        best_ratio: float = 0.0,
        best_y: int = -1,
    ) -> None:
        """生成滑块调试预览图并发射信号 — 委托 DebugPreview"""
        debug_rgb = DebugPreview.generate_slider_debug(
            img, region_x, top_y, bottom_y,
            region_w, region_h, slider_y, label, best_ratio, best_y,
        )
        key = "slider_debug"
        PreviewImageProvider.put(key, debug_rgb)
        self.debugPreviewReady.emit(key)

    @Slot()
    def captureGrayscalePreview(self) -> None:
        """截图并以灰度图显示在预览窗口中 — 委托 DebugPreview"""
        result = self._capture.capture()
        if result is None:
            log.warning("灰度截图: 无法捕获原神窗口")
            return
        debug_rgb = DebugPreview.generate_grayscale(result.image)
        key = "grayscale_snapshot"
        PreviewImageProvider.put(key, debug_rgb)
        self.debugPreviewReady.emit(key)
        log.info(f"灰度截图: {result.image.shape[1]}x{result.image.shape[0]}")

    @Slot(int, int, int, int, int, int, int)
    def detectSlots(
        self,
        roi_x: int, roi_y: int, roi_w: int, roi_h: int,
        white_threshold: int, tolerance: int, top_offset: int,
    ) -> None:
        """截图并检测圣遗物格子，生成调试预览图"""
        result = self._capture.capture()
        if result is None:
            log.warning("格子检测: 无法捕获原神窗口")
            return

        roi = (roi_x, roi_y, roi_w, roi_h) if roi_w > 0 and roi_h > 0 else None
        slots = SlotDetector.detect(
            result.image, roi=roi,
            white_threshold=white_threshold, tolerance=tolerance,
            top_offset=top_offset,
        )
        log.info(f"格子检测: 找到 {len(slots)} 个格子")

        debug_rgb = SlotDetector.draw_debug(result.image, slots, roi=roi)
        key = "slot_debug"
        PreviewImageProvider.put(key, debug_rgb)
        self.debugPreviewReady.emit(key)