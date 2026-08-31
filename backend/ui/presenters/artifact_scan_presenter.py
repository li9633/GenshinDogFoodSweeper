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

import numpy as np
from models.artifact import ArtifactInfo
from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot
from ui.lifecycle import OnWindowReady
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
from backend.automation.slot_detector import (
    ALL_SLOT_CONFIGS,
    BAG_SLOT_CONFIG,
    SlotDetector,
)
from backend.automation.smart_scroller import SmartScroller
from backend.automation.window_helper import WindowHelper
from backend.exceptions.automation import OcrModelNotReadyError
from backend.utils.screen_capture import ScreenshotCapture
from backend.utils.settings_manager import settings

from .image_provider import PreviewImageProvider


class ArtifactScanPresenter(QObject, OnWindowReady):
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
    fullScanSavedPathChanged = Signal()

    # 扫描选项变更
    scanOptionsChanged = Signal()

    # 格子检测配置切换
    activeConfigChanged = Signal()

    def __init__(self, parent: QObject | None = None):
        QObject.__init__(self, parent)
        OnWindowReady.__init__(self)
        self._mouse = MouseController()

    def on_window_ready(self) -> None:
        """窗口就绪后初始化（OCR Worker 由 OcrInitializer 统一管理）"""
        self._capture = ScreenshotCapture()
        self._win_helper = WindowHelper(self._capture)
        MouseController.set_window_helper(self._win_helper)

        self._available_configs = ALL_SLOT_CONFIGS
        self._active_config = BAG_SLOT_CONFIG
        self._active_config_index = 0

        self._slider_scroller = SliderScroller(
            self._mouse,
            self._capture,
            self._win_helper,
            self._active_config,
            debug_callback=self._emit_slider_debug,
        )

        # 批量点击
        self._batch_progress = ""
        self._batch_running = False
        self._batch_worker: BatchClickWorker | None = None

        # 操作参数（非 SlotDetectorConfig，留作将来可配置化）
        self._grid_gap = 24
        self._batch_click_interval = 100
        self._full_scan_click_interval = 150
        self._scroll_flag_x = 230
        self._scroll_flag_y = 335
        self._scroll_tick_delay = 30
        self._scroll_page_settle = 200

        self._page_scroller = PageScroller(self._mouse, self._capture)

        # 首尾锚点
        self._anchor_first_x = 0
        self._anchor_first_y = 0
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
        self._full_scan_saved_path: str = ""

        # 格子检测配置
        self._available_configs = ALL_SLOT_CONFIGS

        # SmartScroller 调试
        self._smart_ruler_x = 0
        self._smart_ruler_y = 0
        self._smart_ruler_w = 10
        self._smart_ruler_h = 200
        self._smart_row_height = 96
        self._smart_scroller: SmartScroller | None = None

    def _get_smart_scroller(self) -> SmartScroller:
        """懒初始化 SmartScroller"""
        if self._smart_scroller is None:
            self._smart_scroller = SmartScroller(
                self._capture,
                self._mouse,
                self._win_helper,
                slider=self._slider_scroller,
                config=self._active_config,
            )
        return self._smart_scroller

    # ==================================================================
    # 内部工具
    # ==================================================================

    def _window_origin(self) -> tuple[int, int]:
        return self._win_helper.get_origin()

    # 操作参数（供 QML 展示，暂不开放修改）

    @Property(int, constant=True)
    def gridGap(self) -> int:
        return self._grid_gap

    @Property(int, constant=True)
    def batchClickInterval(self) -> int:
        return self._batch_click_interval

    @Property(int, constant=True)
    def fullScanClickInterval(self) -> int:
        return self._full_scan_click_interval

    @Property(int, constant=True)
    def scrollFlagX(self) -> int:
        return self._scroll_flag_x

    @Property(int, constant=True)
    def scrollFlagY(self) -> int:
        return self._scroll_flag_y

    @Property(int, constant=True)
    def scrollTickDelay(self) -> int:
        return self._scroll_tick_delay

    @Property(int, constant=True)
    def scrollPageSettle(self) -> int:
        return self._scroll_page_settle

    # ==================================================================
    # 扫描选项（扫描前设置，同步到 settings）
    # ==================================================================

    @Property(bool, notify=scanOptionsChanged)
    def scanEnableDedup(self) -> bool:
        return settings.get_bool("scan.enable_dedup")

    @Slot(bool)
    def setScanEnableDedup(self, value: bool) -> None:
        settings.set("scan.enable_dedup", "true" if value else "false")
        self.scanOptionsChanged.emit()

    @Property(str, notify=scanOptionsChanged)
    def scanStopMode(self) -> str:
        return settings.get("scan.stop_mode")

    @Slot(str)
    def setScanStopMode(self, value: str) -> None:
        settings.set("scan.stop_mode", value)
        self.scanOptionsChanged.emit()

    _STOP_MODE_KEYS = ("anchor", "five_star_only", "fixed_count")

    @Property(int, notify=scanOptionsChanged)
    def scanStopModeIndex(self) -> int:
        mode = self.scanStopMode or "anchor"
        try:
            return self._STOP_MODE_KEYS.index(mode)
        except ValueError:
            return 0

    @Slot(int)
    def setScanStopModeByIndex(self, index: int) -> None:
        if 0 <= index < len(self._STOP_MODE_KEYS):
            self.setScanStopMode(self._STOP_MODE_KEYS[index])

    @Property(int, notify=scanOptionsChanged)
    def scanFixedCount(self) -> int:
        return settings.get_int("scan.fixed_count")

    @Slot(int)
    def setScanFixedCount(self, value: int) -> None:
        settings.set("scan.fixed_count", str(value))
        self.scanOptionsChanged.emit()

    # ==================================================================
    # 批量点击
    # ==================================================================

    @Property(str, notify=batchProgressChanged)
    def batchProgress(self) -> str:
        return self._batch_progress

    @Property(bool, notify=batchRunningChanged)
    def batchRunning(self) -> bool:
        return self._batch_running

    @Slot()
    def startBatchClick(self) -> None:
        """批量点击：参数从当前 SlotDetectorConfig 读取"""
        if self._batch_running:
            return
        ox, oy = self._window_origin()
        if ox == 0 and oy == 0:
            log.warning("未检测到原神窗口")
            return

        cfg = self._active_config
        roi = cfg.roi or (0, 0, 0, 0)
        rows, cols = cfg.rows, cfg.cols
        self._batch_worker = BatchClickWorker(
            mouse=self._mouse,
            config=GridClickConfig(
                origin_x=ox,
                origin_y=oy,
                margin_x=roi[0],
                margin_y=roi[1],
                item_w=cfg.slot_w,
                item_h=cfg.slot_h,
                gap=self._grid_gap,
                rows=rows,
                cols=cols,
                interval_ms=self._batch_click_interval,
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
        log.info(f"批量点击开始: {rows}×{cols} 网格, 配置={cfg.name}")

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
        self._win_helper.focus()
        ox, oy = self._window_origin()
        if ox == 0 and oy == 0:
            log.warning("未检测到原神窗口")
            return
        self._page_scroller.set_config(self._active_config)
        self._page_scroller.scroll_to_next_page(
            ox,
            oy,
            flag_x,
            flag_y,
            tick_delay_ms=scroll_delay_ms,
        )
        log.info("格子翻页完成")

    @Slot(int, int, int)
    def scrollPageToBottom(
        self, flag_x: int, flag_y: int, scroll_delay_ms: int = 80
    ) -> None:
        """自动翻到底：OCR 识别数量 → 计算总页数 → 循环 截图→检测→滚动。"""
        self._win_helper.focus()
        ox, oy = self._window_origin()
        if ox == 0 and oy == 0:
            log.warning("未检测到原神窗口")
            return

        # OCR 识别圣遗物数量，计算总页数
        engines_dir = Path(__file__).resolve().parents[3] / "engines"
        try:
            ocr = OcrEngine.create_ocr(engines_dir)
        except OcrModelNotReadyError:
            return
        count = ocr_artifact_count(self._capture, ocr)
        total_pages = max(1, (count + 31) // 32) if count > 0 else 0
        max_pages = total_pages - 1 if total_pages > 0 else 0
        log.info(
            f"自动翻到底开始... 圣遗物数量={count}, 总页数={total_pages}, 安全上限={max_pages}"
        )
        self._page_scroller.set_config(self._active_config)
        pages = self._page_scroller.scroll_to_bottom(
            ox,
            oy,
            flag_x,
            flag_y,
            tick_delay_ms=scroll_delay_ms,
            max_pages=max_pages,
            total_pages=total_pages,
        )
        log.info(f"自动翻到底完成: 共翻页 {pages} 次")

    # ==================================================================
    # 格子检测配置切换
    # ==================================================================

    @Property("QVariantList", notify=activeConfigChanged)
    def availableConfigNames(self) -> list[str]:
        return [c.name for c in self._available_configs]

    @Property(int, notify=activeConfigChanged)
    def activeConfigIndex(self) -> int:
        return self._active_config_index

    @Property(int, notify=activeConfigChanged)
    def activeConfigRoiX(self) -> int:
        roi = self._active_config.roi
        return roi[0] if roi else 0

    @Property(int, notify=activeConfigChanged)
    def activeConfigRoiY(self) -> int:
        roi = self._active_config.roi
        return roi[1] if roi else 0

    @Property(int, notify=activeConfigChanged)
    def activeConfigRoiW(self) -> int:
        roi = self._active_config.roi
        return roi[2] if roi else 0

    @Property(int, notify=activeConfigChanged)
    def activeConfigRoiH(self) -> int:
        roi = self._active_config.roi
        return roi[3] if roi else 0

    @Property(bool, notify=activeConfigChanged)
    def activeConfigHasCount(self) -> bool:
        return self._active_config.has_artifact_count

    @Property(str, notify=activeConfigChanged)
    def activeConfigName(self) -> str:
        return self._active_config.name

    @Property(int, notify=activeConfigChanged)
    def activeConfigCols(self) -> int:
        return self._active_config.cols

    @Property(int, notify=activeConfigChanged)
    def activeConfigRows(self) -> int:
        return self._active_config.rows

    @Property(int, notify=activeConfigChanged)
    def activeConfigSlotW(self) -> int:
        return self._active_config.slot_w

    @Property(int, notify=activeConfigChanged)
    def activeConfigSlotH(self) -> int:
        return self._active_config.slot_h

    @Property(int, notify=activeConfigChanged)
    def activeConfigLeftOffset(self) -> int:
        return self._active_config.roi_left_offset

    @Property(int, notify=activeConfigChanged)
    def activeConfigRightOffset(self) -> int:
        return self._active_config.roi_right_offset

    @Property(int, notify=activeConfigChanged)
    def activeConfigTopOffset(self) -> int:
        return self._active_config.top_offset

    @Property(int, notify=activeConfigChanged)
    def activeConfigWhiteThreshold(self) -> int:
        return self._active_config.white_threshold

    @Property(int, notify=activeConfigChanged)
    def activeConfigTolerance(self) -> int:
        return self._active_config.tolerance

    @Slot(int)
    def setActiveConfigByIndex(self, index: int) -> None:
        if 0 <= index < len(self._available_configs):
            self._active_config = self._available_configs[index]
            self._active_config_index = index
            self._page_scroller.set_config(self._active_config)
            log.info(f"格子检测配置切换: {self._active_config.name}")
            self.activeConfigChanged.emit()

    # ==================================================================
    # 首尾锚点定位
    # ==================================================================

    @Property(int, notify=anchorFirstMarked)
    def anchorFirstX(self) -> int:
        return self._anchor_first_x

    @Property(int, notify=anchorFirstMarked)
    def anchorFirstY(self) -> int:
        return self._anchor_first_y

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

    @Slot()
    def recognizeFirstAnchor(self) -> None:
        """识别首锚点：截图 → 格子检测 → 取第一个格子 → 点击 → OCR"""
        result = self._capture.capture()
        if result is None:
            log.warning("首锚点识别: 截图失败")
            return
        cfg = self._active_config
        det_result = SlotDetector.detect(result.image, config=cfg)
        if not det_result.slots:
            log.warning("首锚点识别: 未检测到格子，请确认已滚动到顶部")
            return
        first = det_result.slots[0]
        cx, cy, sx, sy = first.cx, first.cy, first.x, first.y
        self._anchor_first_x = sx
        self._anchor_first_y = sy
        self._anchor_first_display_text = ""
        self._anchor_first_recognized = False
        self.anchorFirstMarked.emit()
        self.anchorFirstRecognizedChanged.emit()
        log.info(f"首锚点已定位: 第1个格子 ({sx}, {sy}), 开始OCR识别...")
        self._recognize_anchor_item(cx, cy, "first")

    def _calculate_anchor_pages(self) -> None:
        """根据首尾锚点计算总页数 — 委托给 AnchorLocator"""
        if self._anchor_first_y == 0 or self._anchor_last_y == 0:
            return
        is_tail_center = self._anchor_tail_y != 0
        rows, pages = AnchorLocator.calculate_pages(
            self._anchor_first_y,
            self._anchor_last_y,
            self._active_config.slot_h,
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
        """识别尾锚点：截图 → 格子检测 → 取最后一个格子 → 点击 → OCR → 计算页数"""
        result = self._capture.capture()
        if result is None:
            log.warning("尾锚点识别: 截图失败")
            return
        cfg = self._active_config
        det_result = SlotDetector.detect(result.image, config=cfg)
        if not det_result.slots:
            log.warning("尾锚点识别: 未检测到格子，请确认已滚动到底部")
            return
        last = det_result.slots[-1]
        cx, cy, sx, sy = last.cx, last.cy, last.x, last.y
        self._anchor_last_x = cx
        self._anchor_last_y = cy
        self._anchor_tail_x = 0
        self._anchor_tail_y = 0
        self._anchor_tail_info = None
        self._anchor_tail_display_text = ""
        self._anchor_tail_recognized = False
        self.anchorLastFound.emit()
        self.anchorTailRecognizedChanged.emit()
        self._calculate_anchor_pages()
        log.info(f"尾锚点已定位: 最后1个格子 ({sx}, {sy}), 开始OCR识别...")
        self._recognize_anchor_item(cx, cy, "tail")

    def _connect_anchor_ocr_worker(self) -> None:
        if self._anchor_ocr_connected:
            return
        from backend.automation.ocr_worker import OcrWorker

        worker = OcrWorker.instance()
        worker.task_done.connect(self._on_anchor_ocr_done)
        worker.task_error.connect(self._on_anchor_ocr_error)
        self._anchor_ocr_connected = True

    def _recognize_anchor_item(
        self,
        cx: int,
        cy: int,
        anchor_type: str,
    ) -> None:
        """点击锚点物品 → 延迟等待详情面板 → 截图 → 提交OCR任务"""
        self._connect_anchor_ocr_worker()
        self._win_helper.focus()
        self._mouse.move_and_click(cx, cy)

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
                result.image,
                roi_configs,
                anchor_type,
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
            structured_lines = ArtifactRecognitionPresenter._format_structured(artifact)
            return {
                "anchor_type": anchor_type,
                "artifact": artifact,
                "display_lines": display_lines,
                "structured_lines": structured_lines,
            }

        return task

    def _on_anchor_ocr_done(
        self,
        result: dict,
        callback_data: object,
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
        self,
        error: str,
        callback_data: object,
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

    @Property(str, notify=fullScanSavedPathChanged)
    def fullScanSavedPath(self) -> str:
        return self._full_scan_saved_path

    @Slot()
    def startFullScan(self) -> None:
        """开始全量圣遗物扫描 — 参数从当前 SlotDetectorConfig 读取"""
        if self._full_scan_running:
            log.warning("全量扫描已在运行中")
            return
        ox, oy = self._window_origin()
        if ox == 0 and oy == 0:
            log.warning("未检测到原神窗口")
            return

        cfg = self._active_config
        roi = cfg.roi or (0, 0, 0, 0)
        engines_dir = Path(__file__).resolve().parents[3] / "engines"

        self._full_scan_results = []
        self._full_scan_saved_path = ""

        log.info("全量扫描开始 (保存目录: scan_result/)")

        def _save_results(results: list[ArtifactInfo]) -> None:
            """扫描完成回调：保存 JSON 到 scan_result/ 目录"""
            import json
            from dataclasses import asdict

            from backend.database.repository.artifact_set_repo import ArtifactSetRepo
            from backend.utils.datetime_helper import DateTimeHelper

            # 一次查询所有套装，构建映射（避免 N 次 DB 连接）
            all_sets = {s.id: s for s in ArtifactSetRepo.find_all()}
            for r in results:
                if r.set_id is not None:
                    artifact_set = all_sets.get(r.set_id)
                    if artifact_set:
                        r.set_effects = artifact_set.set_effects

            out_dir = Path(__file__).resolve().parents[3] / "scan_result"
            out_dir.mkdir(parents=True, exist_ok=True)
            filename = f"scan_{DateTimeHelper.file_timestamp()}.json"
            filepath = out_dir / filename
            data = [asdict(r) for r in results]
            for d in data:
                d.pop("raw_texts", None)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self._full_scan_saved_path = str(filepath)
            self.fullScanSavedPathChanged.emit()
            log.info(f"扫描结果已保存: {filepath} ({len(data)} 件)")

        self._full_scan_worker = FullScanWorker(
            mouse=self._mouse,
            capture=self._capture,
            engines_dir=engines_dir,
            margin_x=roi[0],
            margin_y=roi[1],
            item_w=cfg.slot_w,
            item_h=cfg.slot_h,
            gap=self._grid_gap,
            anchor_first_x=self._anchor_first_x or roi[0],
            anchor_first_y=self._anchor_first_y or roi[1],
            anchor_first_w=cfg.slot_w,
            anchor_first_h=cfg.slot_h,
            slot_config=cfg,
            scroll_flag_x=self._scroll_flag_x,
            scroll_flag_y=self._scroll_flag_y,
            tick_delay_ms=self._scroll_tick_delay,
            page_settle_ms=self._scroll_page_settle,
            click_interval_ms=self._full_scan_click_interval,
            stop_mode=settings.get("scan.stop_mode") or "anchor",
            on_complete=_save_results,
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

    @Slot()
    def stopAllOperations(self) -> None:
        """全局热键 → 终止所有正在运行的自动化操作"""
        stopped = False
        if self._full_scan_running:
            self.stopFullScan()
            stopped = True
        if self._batch_running:
            self.stopBatchClick()
            stopped = True
        if self._anchor_scroll_running:
            if self._scroll_to_bottom_worker is not None:
                self._scroll_to_bottom_worker.stop()
            self._anchor_scroll_running = False
            self.anchorScrollRunningChanged.emit()
            stopped = True
        if stopped:
            log.info("热键终止: 已停止所有自动化操作")
        else:
            log.debug("热键终止: 无正在运行的操作")

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
        stop_mode = settings.get("scan.stop_mode") or "anchor"
        if stop_mode == "fixed_count":
            log.info(f"全量扫描完成: 固定数量{scanned}个")
        else:
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

    @Slot()
    def scrollToBottom(self) -> None:
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

        slider_y = self._slider_scroller.ensure_at_top()
        if slider_y is None:
            return

        window = self._capture.find_genshin_window()
        window_bottom = (oy + window.height) if window else (oy + 1000)

        self._scroll_to_bottom_worker = SmartScrollToBottomWorker(
            mouse=self._mouse,
            capture=self._capture,
            ox=ox,
            oy=oy,
            slot_config=self._active_config,
            initial_slider_y=slider_y,
            window_bottom=window_bottom,
        )
        self._scroll_to_bottom_worker.progress.connect(self._onScrollToBottomProgress)
        self._scroll_to_bottom_worker.final_slider_y.connect(
            self._on_smart_scroll_final_slider_y
        )
        self._scroll_to_bottom_worker.finished.connect(self._onScrollToBottomFinished)
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
        det_result = SlotDetector.detect(result.image, config=self._active_config)
        if not det_result.slots:
            log.warning("尾锚点定位: 未检测到格子")
            return
        # slots 按 y 再 x 排序，最后一个即为右下角尾锚点
        last_slot = det_result.slots[-1]
        tail_cx, tail_cy = last_slot.cx, last_slot.cy
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

    @Slot()
    def checkScrollBottomByColor(self) -> None:
        """颜色检测是否到底 — 委托 SliderScroller"""
        slider_y, is_at_bottom = self._slider_scroller.check_bottom_by_color()
        if slider_y is None:
            return
        if is_at_bottom:
            sr = self._active_config.slider_region()
            if sr is None:
                return
            region_x, _top_y, region_y, region_w, region_h = sr
            log.info(f"追加{SliderDetector.EXTRA_TICKS}次滚动确保100%到底")
            ox, oy = self._window_origin()
            if ox != 0 or oy != 0:
                self._mouse.move_to(
                    region_x + region_w // 2,
                    region_y + region_h // 2,
                )
                for _ in range(SliderDetector.EXTRA_TICKS):
                    self._mouse.scroll_one_tick()
                    sleep(0.03)
            log.info("颜色检测: 已确认到底，追加滚动完成")

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
            img,
            region_x,
            top_y,
            bottom_y,
            region_w,
            region_h,
            slider_y,
            label,
            best_ratio,
            best_y,
        )
        key = "slider_debug"
        vkey = PreviewImageProvider.put(key, debug_rgb)
        self.debugPreviewReady.emit(vkey)

    @Slot()
    def captureGrayscalePreview(self) -> None:
        """截图并以灰度图显示在预览窗口中 — 委托 DebugPreview"""
        result = self._capture.capture()
        if result is None:
            log.warning("灰度截图: 无法捕获原神窗口")
            return
        debug_rgb = DebugPreview.generate_grayscale(result.image)
        key = "grayscale_snapshot"
        vkey = PreviewImageProvider.put(key, debug_rgb)
        self.debugPreviewReady.emit(vkey)
        log.info(f"灰度截图: {result.image.shape[1]}x{result.image.shape[0]}")

    @Slot(int, int, int)
    def navigateToSlot(self, page: int, row: int, col: int) -> None:
        """定位到指定圣遗物格子：到顶 → 校准 → 计算 → 到顶 → 滚动

        SmartScroller 流程: 先通过滑块到顶，校准 pixels_per_scroll，
        重新到顶（消除校准滚动的偏移），再根据目标行数一次性滚动到位。
        """
        cfg = self._active_config
        roi = cfg.roi
        if roi is None:
            return
        rx, ry, rw, rh = roi

        ox, oy = self._window_origin()
        if ox == 0 and oy == 0:
            log.warning("定位失败: 未检测到原神窗口")
            return

        self._win_helper.focus()

        sc = self._get_smart_scroller()

        # 1. 滚动到顶
        if not sc.scroll_to_top():
            log.warning("定位失败: 无法滚动到顶")
            return

        # 2. 校准 pixels_per_scroll
        sc.calibrate()

        # 3. 计算目标行数（滚动到目标页起始位置，页内由格子检测定位）
        total_rows = page * cfg.rows

        # 4. 强制到顶（校准滚动偏移极小，需强制拖拽）
        sc.scroll_to_top(force=True)

        # 5. 滚动到目标行
        sc.scroll_rows(total_rows)

        # 6. 截图 + 格子检测 → 点击
        result = self._capture.capture()
        if result is None:
            log.warning("定位失败: 无法捕获截图")
            return

        det_result = SlotDetector.detect(result.image, config=cfg)
        if row >= cfg.rows or col >= cfg.cols:
            log.warning(f"定位失败: 行列({row},{col})超出范围({cfg.rows}x{cfg.cols})")
            return

        col_lefts, col_rights, row_bottoms, _, _ = SlotDetector._compute_grid(
            (rx, ry, rw, rh),
            cfg,
            det_result.bottom_y,
        )
        cx = (col_lefts[col] + col_rights[col]) // 2
        cy = row_bottoms[row] - cfg.slot_h // 2
        self._mouse.move_and_click(cx, cy)
        log.info(f"定位完成: P{page}R{row}C{col} → 窗口相对({cx}, {cy})")

    @Slot()
    def detectSlots(self) -> None:
        """截图并检测圣遗物格子，使用当前选中配置，生成调试预览图"""
        result = self._capture.capture()
        if result is None:
            log.warning("格子检测: 无法捕获原神窗口")
            return

        cfg = self._active_config
        det_result = SlotDetector.detect(
            result.image,
            config=cfg,
        )
        log.info(f"格子检测: 找到 {len(det_result.slots)} 个格子 [{cfg.name}]")

        debug_rgb = SlotDetector.draw_debug(
            result.image,
            det_result.slots,
            config=cfg,
            page_bottom=det_result.bottom_y,
            debug_infos=det_result.debug_infos,
        )
        key = "slot_debug"
        vkey = PreviewImageProvider.put(key, debug_rgb)
        self.debugPreviewReady.emit(vkey)

    # ==================================================================
    # SmartScroller 调试
    # ==================================================================

    # -- 标尺配置 --

    @Slot(int)
    def setSmartRulerX(self, value: int) -> None:
        self._smart_ruler_x = value
        self._smart_scroller = None

    @Slot(int)
    def setSmartRulerY(self, value: int) -> None:
        self._smart_ruler_y = value
        self._smart_scroller = None

    @Slot(int)
    def setSmartRulerW(self, value: int) -> None:
        self._smart_ruler_w = value
        self._smart_scroller = None

    @Slot(int)
    def setSmartRulerH(self, value: int) -> None:
        self._smart_ruler_h = value
        self._smart_scroller = None

    @Slot(int)
    def setSmartRowHeight(self, value: int) -> None:
        self._smart_row_height = value
        self._smart_scroller = None

    # -- 属性 --

    smartCalibratedChanged = Signal()
    smartPixelsPerScrollChanged = Signal()

    @Property(bool, notify=smartCalibratedChanged)
    def smartCalibrated(self) -> bool:
        return self._smart_scroller.is_calibrated if self._smart_scroller else False

    @Property(float, notify=smartPixelsPerScrollChanged)
    def smartPixelsPerScroll(self) -> float:
        return self._smart_scroller.pixels_per_scroll if self._smart_scroller else 0.0

    @Property(int, notify=smartPixelsPerScrollChanged)
    def smartCurrentRow(self) -> int:
        return self._smart_scroller.current_row if self._smart_scroller else 0

    # -- 操作 --

    @Slot()
    def smartCalibrate(self) -> None:
        try:
            sc = self._get_smart_scroller()
            sc.calibrate()
            self.smartCalibratedChanged.emit()
            self.smartPixelsPerScrollChanged.emit()
        except RuntimeError as e:
            log.warning(f"SmartScroll校准失败: {e}")

    @Slot()
    def smartScrollToTop(self) -> None:
        sc = self._get_smart_scroller()
        sc.scroll_to_top()
        self.smartPixelsPerScrollChanged.emit()

    @Slot(int)
    def smartScrollRows(self, rows: int) -> None:
        sc = self._get_smart_scroller()
        sc.scroll_rows(rows)
        self.smartPixelsPerScrollChanged.emit()

    @Slot()
    def smartReset(self) -> None:
        if self._smart_scroller:
            self._smart_scroller.reset()
            self.smartPixelsPerScrollChanged.emit()

    @Slot()
    def smartMeasureRowHeight(self) -> None:
        """在顶部检测行高，生成预览图 — 委托 SlotDetector"""
        result = self._capture.capture()
        if result is None:
            log.warning("SmartScroll 行高测量: 截图失败")
            return
        det = SlotDetector.detect(result.image, config=self._active_config)
        if det.row_height <= 0:
            log.warning("SmartScroll 行高测量失败: 未检测到格子")
            return
        sc = self._get_smart_scroller()
        sc._row_height = det.row_height
        debug_rgb = SlotDetector.generate_row_height_debug(
            result.image,
            det,
            config=self._active_config,
        )
        vkey = PreviewImageProvider.put("smart_scroll", debug_rgb)
        self.debugPreviewReady.emit(vkey)
        log.info(f"SmartScroll 行高已更新: {det.row_height}px")