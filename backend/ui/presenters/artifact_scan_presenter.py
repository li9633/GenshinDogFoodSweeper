"""
圣遗物扫描 Presenter
====================
将鼠标操作暴露给 QML 调试面板，用于测试圣遗物定位、点击与精准翻页功能。
"""

from __future__ import annotations

import re

import cv2
import numpy as np
from PySide6.QtCore import Property, QObject, QThread, Signal, Slot
from utils.logger import log

from backend.automation.mouse_controller import MouseController
from backend.automation.template_matcher import find_all_matches
from backend.utils.screen_capture import ScreenshotCapture
from models.artifact import ArtifactInfo

from .image_provider import PreviewImageProvider


class _BatchClickWorker(QThread):
    """后台线程：逐行逐列点击圣遗物"""

    progress = Signal(int, int)  # (current, total)
    finished = Signal()

    def __init__(
        self,
        mouse: MouseController,
        origin_x: int,
        origin_y: int,
        margin_x: int,
        margin_y: int,
        item_w: int,
        item_h: int,
        gap: int,
        rows: int,
        cols: int,
        interval_ms: int = 100,
    ):
        super().__init__()
        self._mouse = mouse
        self._origin_x = origin_x
        self._origin_y = origin_y
        self._margin_x = margin_x
        self._margin_y = margin_y
        self._item_w = item_w
        self._item_h = item_h
        self._gap = gap
        self._rows = rows
        self._cols = cols
        self._interval_ms = interval_ms
        self._stop = False

    def stop(self) -> None:
        self._stop = True

    def run(self) -> None:
        from time import sleep

        total = self._rows * self._cols
        current = 0

        for row in range(self._rows):
            if self._stop:
                break
            for col in range(self._cols):
                if self._stop:
                    break

                # 定位公式：点击每个圣遗物图标中心
                x = (
                    self._origin_x
                    + self._margin_x
                    + (self._gap + self._item_w) * col
                    + self._item_w // 2
                )
                y = (
                    self._origin_y
                    + self._margin_y
                    + (self._gap + self._item_h) * row
                    + self._item_h // 2
                )

                self._mouse.move_and_click(x, y)
                current += 1
                self.progress.emit(current, total)
                sleep(self._interval_ms / 1000.0)

        self.finished.emit()


class _ScrollOneRowWorker(QThread):
    """后台线程：滚动固定格数（10 格 = 1 行）"""

    progress = Signal(int)  # 当前已滚格数
    finished = Signal()

    TICKS_PER_ROW = 10

    def __init__(
        self,
        mouse: MouseController,
        flag_x: int,
        flag_y: int,
        delay_ms: int,
        origin_x: int,
        origin_y: int,
    ):
        super().__init__()
        self._mouse = mouse
        self._flag_x = flag_x
        self._flag_y = flag_y
        self._delay_ms = delay_ms
        self._origin_x = origin_x
        self._origin_y = origin_y

    def run(self) -> None:
        from time import sleep

        for i in range(1, self.TICKS_PER_ROW + 1):
            self._mouse.move_to(
                self._origin_x + self._flag_x,
                self._origin_y + self._flag_y,
            )
            self._mouse.scroll_one_tick()
            self.progress.emit(i)
            sleep(self._delay_ms / 1000.0)

        self.finished.emit()


class _AutoScrollWorker(QThread):
    """后台线程：自动翻页，逐页滚动直到最后一页"""

    progress = Signal(int, int)  # (current_page, total_pages)
    finished = Signal()

    ROWS_PER_PAGE = 4

    def __init__(
        self,
        mouse: MouseController,
        origin_x: int,
        origin_y: int,
        flag_x: int,
        flag_y: int,
        total_pages: int,
        ticks_per_row: int,
        tick_delay_ms: int,
        page_settle_ms: int,
    ):
        super().__init__()
        self._mouse = mouse
        self._origin_x = origin_x
        self._origin_y = origin_y
        self._flag_x = flag_x
        self._flag_y = flag_y
        self._total_pages = total_pages
        self._ticks_per_row = ticks_per_row
        self._tick_delay_ms = tick_delay_ms
        self._page_settle_ms = page_settle_ms
        self._stop = False

    def stop(self) -> None:
        self._stop = True

    def run(self) -> None:
        from time import sleep

        ticks_per_page = self._ticks_per_row * self.ROWS_PER_PAGE
        for page in range(1, self._total_pages):
            if self._stop:
                break

            for _ in range(ticks_per_page):
                if self._stop:
                    break
                self._mouse.move_to(
                    self._origin_x + self._flag_x,
                    self._origin_y + self._flag_y,
                )
                self._mouse.scroll_one_tick()
                sleep(self._tick_delay_ms / 1000.0)

            if self._stop:
                break

            log.info(f"自动翻页: 当前 {page + 1} 页，共 {self._total_pages} 页")
            self.progress.emit(page + 1, self._total_pages)

            if page < self._total_pages - 1:
                sleep(self._page_settle_ms / 1000.0)

        self.finished.emit()


class _SmartScrollToBottomWorker(QThread):
    """智能拖拽到底部：计算滑轨长度 → 大距离拖拽 → 快速到底"""

    DRAG_CHUNKS = 3  # 分3次拖拽
    DRAG_STEPS = 10  # 每块拖拽步数
    DRAG_STEP_DELAY = 15  # 每步延迟（ms）
    DRAG_RATIO = 4  # 鼠标拖拽距离 / 滑块移动距离（经验值 ~3.5）

    progress = Signal(int)
    final_slider_y = Signal(int)
    finished = Signal()

    def __init__(
        self,
        mouse: MouseController,
        capture: ScreenshotCapture,
        ox: int,
        oy: int,
        region_x: int,
        region_y: int,
        region_w: int,
        region_h: int,
        initial_slider_y: int,
        window_bottom: int,
    ):
        super().__init__()
        self._mouse = mouse
        self._capture = capture
        self._ox = ox
        self._oy = oy
        self._region_x = region_x
        self._region_y = region_y
        self._region_w = region_w
        self._region_h = region_h
        self._initial_slider_y = initial_slider_y
        self._window_bottom = window_bottom
        self._stop = False

    def stop(self) -> None:
        self._stop = True

    def run(self) -> None:
        from time import sleep

        prev_y = self._initial_slider_y
        drag_x = self._ox + self._region_x + self._region_w // 2

        # 计算滑块需要移动的总距离
        slider_total = self._region_y - self._initial_slider_y
        if slider_total <= 0:
            log.info("智能拖拽: 滑块已在底部，跳过")
            self.final_slider_y.emit(self._initial_slider_y)
            self.finished.emit()
            return

        # 鼠标需要拖拽的距离（补偿鼠标-滑块移动比例）
        mouse_total = slider_total * self.DRAG_RATIO
        chunk = mouse_total // self.DRAG_CHUNKS

        log.info(
            f"智能拖拽: 滑块需移动{slider_total}px, "
            f"鼠标拖拽{mouse_total}px, 分{self.DRAG_CHUNKS}次"
        )

        for i in range(self.DRAG_CHUNKS):
            if self._stop:
                break

            drag_from_y = self._oy + prev_y + self._region_h // 2
            drag_to_y = min(drag_from_y + chunk, self._window_bottom - 10)

            self._mouse.drag(
                drag_x, drag_from_y,
                drag_x, drag_to_y,
                self.DRAG_STEPS, self.DRAG_STEP_DELAY,
            )
            sleep(0.2)

            self.progress.emit(i + 1)

            # 检查是否到底
            result = self._capture.capture()
            if result is None:
                continue

            current_y, _, _, _ = ArtifactScanPresenter._find_slider(
                result.image, self._region_x,
                max(0, self._region_y - ArtifactScanPresenter._BOTTOM_MAX_SEARCH),
                self._region_y,
                self._region_w, self._region_h,
            )

            if current_y is None:
                continue

            log.info(
                f"智能拖拽: 第{i + 1}/{self.DRAG_CHUNKS}次 "
                f"(prev={prev_y} → cur={current_y})"
            )

            if self._region_y - current_y <= 5:
                log.info("智能拖拽: 已到底")
                break

            if abs(current_y - prev_y) <= 5:
                log.info(
                    f"智能拖拽: 滑块已停止 "
                    f"(prev={prev_y}, cur={current_y}), 确认到底"
                )
                break

            prev_y = current_y

        self.final_slider_y.emit(prev_y)
        self.finished.emit()


# 锚点识别 ROI 区域定义（相对于游戏窗口，用于识别圣遗物详情面板）
_ANCHOR_ROI_DEFINITIONS = [
    ("圣遗物等级", 1338, 452, 71, 44),
    ("圣遗物星级", 1742, 159, 39, 40),
    ("圣遗物名称", 1329, 144, 262, 62),
    ("部位+主词条", 1339, 214, 160, 174),
    ("副词条区", 1347, 498, 276, 166),
]


class ArtifactScanPresenter(QObject):
    """圣遗物扫描 — 注册为 QML context property

    QML 传入的坐标是相对于原神窗口左上角的偏移，
    内部自动转换为屏幕绝对坐标后调用 MouseController。
    """

    batchProgressChanged = Signal()
    batchRunningChanged = Signal()
    scrollStateChanged = Signal()

    # 自动翻页
    detectedCountChanged = Signal()
    detectedTotalPagesChanged = Signal()
    autoScanProgressChanged = Signal()
    autoScanRunningChanged = Signal()

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

    # 翻页
    SCROLL_TICKS_PER_ROW = 10
    ARTIFACTS_PER_PAGE = 32  # 4 行 × 8 列

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._mouse = MouseController()
        self._capture = ScreenshotCapture()
        self._batch_progress = ""
        self._batch_running = False
        self._worker: _BatchClickWorker | None = None
        self._scroll_worker: _ScrollOneRowWorker | None = None
        self._scroll_ticks = 0
        self._scroll_running = False

        # 自动翻页
        self._auto_scroll_worker: _AutoScrollWorker | None = None
        self._detected_count = 0
        self._detected_total_pages = 0
        self._auto_scan_progress = ""
        self._auto_scan_running = False
        self._ocr_connected = False

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
        self._scroll_to_bottom_worker: _SmartScrollToBottomWorker | None = None
        self._scrollbar_track_height = 760

        # 锚点OCR识别
        self._anchor_ocr_connected = False
        self._anchor_first_display_text = ""
        self._anchor_tail_display_text = ""
        self._anchor_first_recognized = False
        self._anchor_tail_recognized = False

    # ========== 内部 ==========

    def _window_origin(self) -> tuple[int, int]:
        window = self._capture.find_genshin_window()
        if window is None:
            return (0, 0)
        return (window.left, window.top)

    def _genshin_hwnd(self) -> int | None:
        window = self._capture.find_genshin_window()
        return window.hwnd if window else None

    def _to_absolute(self, x: int, y: int) -> tuple[int, int]:
        ox, oy = self._window_origin()
        return (ox + x, oy + y)

    # ========== QML 属性 ==========

    # ========== 公开 Slot ==========

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
        hwnd = self._genshin_hwnd()
        if hwnd is None:
            log.warning("未检测到原神窗口")
            return
        ok = self._mouse.focus_window(hwnd)
        log.info(f"聚焦原神窗口: {'成功' if ok else '失败'}")

    @Slot(int, int)
    def moveAndClick(self, x: int, y: int) -> None:
        self.clickAt(x, y)

    @Slot(int)
    def scrollWheel(self, clicks: int) -> None:
        ok = self._mouse.scroll(clicks)
        log.info(f"滚轮: {clicks} {'成功' if ok else '失败'}")

    # ========== 批量点击 ==========

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

        self._worker = _BatchClickWorker(
            mouse=self._mouse,
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
        )
        self._worker.progress.connect(self._on_batch_progress)
        self._worker.finished.connect(self._on_batch_finished)

        self._batch_running = True
        self._batch_progress = "0/" + str(rows * cols)
        self.batchRunningChanged.emit()
        self.batchProgressChanged.emit()

        self._worker.start()
        log.info(f"批量点击开始: {rows}×{cols} 网格, 间隔={interval_ms}ms")

    @Slot()
    def stopBatchClick(self) -> None:
        if self._worker is not None:
            self._worker.stop()
        log.info("批量点击已停止")

    def _on_batch_progress(self, current: int, total: int) -> None:
        self._batch_progress = f"{current}/{total}"
        self.batchProgressChanged.emit()

    def _on_batch_finished(self) -> None:
        self._batch_running = False
        self._worker = None
        self.batchRunningChanged.emit()
        log.info("批量点击完成")

    # ========== 精准翻页（固定 10 格 = 1 行） ==========

    @Property(int, notify=scrollStateChanged)
    def scrollTicks(self) -> int:
        return self._scroll_ticks

    @Property(bool, notify=scrollStateChanged)
    def scrollRunning(self) -> bool:
        return self._scroll_running

    @Slot(int, int, int)
    def scrollOneRow(self, flag_x: int, flag_y: int, scroll_delay_ms: int = 80) -> None:
        """精准滚一行：固定滚 10 格"""
        self.focusGame()

        ox, oy = self._window_origin()
        if ox == 0 and oy == 0:
            log.warning("未检测到原神窗口")
            return

        self._scroll_running = True
        self._scroll_ticks = 0
        self.scrollStateChanged.emit()

        self._scroll_worker = _ScrollOneRowWorker(
            mouse=self._mouse,
            flag_x=flag_x,
            flag_y=flag_y,
            delay_ms=scroll_delay_ms,
            origin_x=ox,
            origin_y=oy,
        )
        self._scroll_worker.progress.connect(self._on_scroll_progress)
        self._scroll_worker.finished.connect(self._on_scroll_finished)
        self._scroll_worker.start()
        log.info(f"精准翻页开始: 锚点({flag_x},{flag_y}), 延迟={scroll_delay_ms}ms")

    def _on_scroll_progress(self, ticks: int) -> None:
        self._scroll_ticks = ticks
        self.scrollStateChanged.emit()

    def _on_scroll_finished(self) -> None:
        self._scroll_running = False
        self._scroll_worker = None
        self.scrollStateChanged.emit()
        log.info(f"翻页完成: 滚了{self._scroll_ticks}格")

    @Slot()
    def resetScrollState(self) -> None:
        """重置翻页状态"""
        self._scroll_ticks = 0
        self._scroll_running = False
        self.scrollStateChanged.emit()
        log.info("翻页状态已重置")

    # ========== 自动翻页（OCR 识别数量 + 逐页滚动） ==========

    @Property(int, notify=detectedCountChanged)
    def detectedCount(self) -> int:
        return self._detected_count

    @Property(int, notify=detectedTotalPagesChanged)
    def detectedTotalPages(self) -> int:
        return self._detected_total_pages

    @Property(str, notify=autoScanProgressChanged)
    def autoScanProgress(self) -> str:
        return self._auto_scan_progress

    @Property(bool, notify=autoScanRunningChanged)
    def autoScanRunning(self) -> bool:
        return self._auto_scan_running

    def _connect_ocr(self) -> None:
        if self._ocr_connected:
            return
        from backend.automation.ocr_worker import OcrWorker

        worker = OcrWorker.instance()
        worker.task_done.connect(self._on_ocr_count_done)
        worker.task_error.connect(self._on_ocr_count_error)
        self._ocr_connected = True

    @Slot(int, int, int, int)
    def ocrCount(self, roi_x: int, roi_y: int, roi_w: int, roi_h: int) -> None:
        """OCR 识别背包圣遗物数量（如 2399/2700 → 提取 2399）"""
        self._connect_ocr()

        window = self._capture.find_genshin_window()
        if window is None:
            log.warning("未检测到原神窗口")
            return

        result = self._capture.capture()
        if result is None:
            log.warning("截图失败")
            return

        img = result.image
        h, w = img.shape[:2]

        x1 = max(0, roi_x)
        y1 = max(0, roi_y)
        x2 = min(w, roi_x + roi_w)
        y2 = min(h, roi_y + roi_h)

        if x2 <= x1 or y2 <= y1:
            log.warning("ROI 区域无效")
            return

        cropped = img[y1:y2, x1:x2].copy()

        def _ocr_task(ocr):
            ocr_result = ocr.ocr(cropped)
            texts: list[str] = []
            if ocr_result and ocr_result[0]:
                r = ocr_result[0]
                if isinstance(r, dict):
                    texts = [t for t in r.get("rec_texts", []) if t and t.strip()]
                elif hasattr(r, "rec_texts"):
                    texts = [t for t in r.rec_texts if t and t.strip()]
            full_text = "".join(texts)
            log.debug(f"OCR 数量识别原始文本: {texts} → \"{full_text}\"")
            # 匹配 "2399/2700" 或 "2399 / 2700" 格式
            m = re.search(r"(\d+)\s*/\s*\d+", full_text)
            if m:
                return int(m.group(1))
            # 回退：尝试匹配纯数字（如 OCR 只识别出 "2399"）
            m2 = re.search(r"\d+", full_text)
            return int(m2.group(0)) if m2 else 0

        from backend.automation.ocr_worker import OcrWorker

        worker = OcrWorker.instance()
        worker.submit(_ocr_task, callback_data="artifact_count")
        log.info(f"OCR 数量识别: ROI=({roi_x},{roi_y},{roi_w},{roi_h})")

    def _on_ocr_count_done(self, count: int, callback_data: object) -> None:
        if callback_data != "artifact_count":
            return
        if not isinstance(count, int):
            return

        self._detected_count = count
        self._detected_total_pages = (
            max(1, (count + self.ARTIFACTS_PER_PAGE - 1) // self.ARTIFACTS_PER_PAGE)
            if count > 0
            else 0
        )
        self.detectedCountChanged.emit()
        self.detectedTotalPagesChanged.emit()

        log.info(
            f"OCR 数量识别完成: {count} 个, {self._detected_total_pages} 页"
        )

    def _on_ocr_count_error(self, error: str, _callback_data: object) -> None:
        log.error(f"OCR 数量识别失败: {error}")

    @Slot(int, int, int, int, int)
    def startAutoScroll(
        self, flag_x: int, flag_y: int, ticks_per_row: int,
        tick_delay_ms: int, page_settle_ms: int,
    ) -> None:
        """开始自动翻页"""
        if self._auto_scan_running:
            return

        if self._detected_total_pages <= 1:
            log.warning("请先 OCR 识别圣遗物数量")
            return

        self.focusGame()

        ox, oy = self._window_origin()
        if ox == 0 and oy == 0:
            log.warning("未检测到原神窗口")
            return

        self._auto_scan_worker = _AutoScrollWorker(
            mouse=self._mouse,
            origin_x=ox,
            origin_y=oy,
            flag_x=flag_x,
            flag_y=flag_y,
            total_pages=self._detected_total_pages,
            ticks_per_row=ticks_per_row,
            tick_delay_ms=tick_delay_ms,
            page_settle_ms=page_settle_ms,
        )
        self._auto_scan_worker.progress.connect(self._on_auto_scan_progress)
        self._auto_scan_worker.finished.connect(self._on_auto_scan_finished)

        self._auto_scan_running = True
        self._auto_scan_progress = f"1/{self._detected_total_pages}"
        self.autoScanRunningChanged.emit()
        self.autoScanProgressChanged.emit()

        self._auto_scan_worker.start()
        log.info(
            f"自动翻页开始: 共 {self._detected_total_pages} 页, "
            f"每行={ticks_per_row}次, 每页={ticks_per_row * 4}次, "
            f"锚点({flag_x},{flag_y}), 滚动延迟={tick_delay_ms}ms, 页面等待={page_settle_ms}ms"
        )

    @Slot()
    def stopAutoScroll(self) -> None:
        """停止自动翻页"""
        if self._auto_scan_worker is not None:
            self._auto_scan_worker.stop()
        log.info("自动翻页已停止")

    def _on_auto_scan_progress(self, current: int, total: int) -> None:
        self._auto_scan_progress = f"{current}/{total}"
        self.autoScanProgressChanged.emit()

    def _on_auto_scan_finished(self) -> None:
        self._auto_scan_running = False
        self._auto_scan_worker = None
        self._auto_scan_progress = "完成"
        self.autoScanRunningChanged.emit()
        self.autoScanProgressChanged.emit()
        log.info("自动翻页完成")

    # ========== 首尾锚点定位 ==========

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

    @Property(int, notify=scrollbarTrackHeightChanged)
    def scrollbarTrackHeight(self) -> int:
        return self._scrollbar_track_height

    @scrollbarTrackHeight.setter
    def scrollbarTrackHeight(self, value: int) -> None:
        if self._scrollbar_track_height != value:
            self._scrollbar_track_height = value
            self.scrollbarTrackHeightChanged.emit()

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

    @Slot(int, int, int, int)
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

        screen_gray = cv2.cvtColor(result.image, cv2.COLOR_RGB2GRAY)
        matches = find_all_matches(screen_gray, self._anchor_first_template, threshold=0.7)

        if not matches:
            self.anchorLastFound.emit()
            log.info("尾锚点查找: 模板匹配未找到结果")
            return

        # 取最底部（Y 最大）的匹配作为尾锚点
        best = matches[-1]
        score, x, y, w, h = best
        self._anchor_last_x = x
        self._anchor_last_y = y
        self.anchorLastFound.emit()
        log.info(
            f"尾锚点已找到: ({x}, {y}) 置信度={score:.2f}, "
            f"共匹配到 {len(matches)} 个位置"
        )

        # 自动计算页数
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
        """根据首尾锚点计算总页数"""
        if self._anchor_first_y == 0 or self._anchor_last_y == 0:
            return

        item_h = self._anchor_first_h
        gap = self._grid_gap
        row_step = item_h + gap
        if row_step <= 0:
            return

        first_center_y = self._anchor_first_y + item_h // 2
        # 新尾锚点（动态定位）的 _anchor_last_y 已经是格子中心；
        # 旧模板匹配的 _anchor_last_y 是格子左上角，需补偿
        if self._anchor_tail_y != 0:
            last_center_y = self._anchor_last_y
        else:
            last_center_y = self._anchor_last_y + item_h // 2

        total_rows = int((last_center_y - first_center_y) / row_step) + 1
        self._anchor_total_rows = total_rows
        self._anchor_total_pages = max(1, (total_rows + 3) // 4)
        self.anchorPagesCalculated.emit()
        log.info(
            f"锚点计算: first=({self._anchor_first_x},{self._anchor_first_y}) "
            f"last=({self._anchor_last_x},{self._anchor_last_y}) "
            f"row_step={row_step} → {total_rows} 行, {self._anchor_total_pages} 页"
        )

    # ========== 锚点 OCR 识别 ==========

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
                for name, dx, dy, dw, dh in _ANCHOR_ROI_DEFINITIONS
            }
            task = self._create_anchor_ocr_task(
                result.image, roi_configs, anchor_type,
            )
            from backend.automation.ocr_worker import OcrWorker

            OcrWorker.instance().submit(task, callback_data=anchor_type)

        from PySide6.QtCore import QTimer

        QTimer.singleShot(200, _capture_and_ocr)

    @staticmethod
    def _create_anchor_ocr_task(image, roi_configs, anchor_type):
        def task(ocr) -> dict:
            from backend.automation.recognizer import ArtifactRecognizer
            from backend.ui.presenters.artifact_recognition_presenter import (
                ArtifactRecognitionPresenter,
            )

            artifact = ArtifactRecognizer.recognize(image, roi_configs, ocr)
            display_lines = (
                ArtifactScanPresenter._format_artifact_display(artifact)
            )
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

    @staticmethod
    def _format_artifact_display(artifact) -> list[str]:
        """将 ArtifactInfo 格式化为简洁的显示文本行"""
        lines: list[str] = []

        if artifact.is_material:
            lines.append("【强化材料】")
            if artifact.material_name:
                lines.append(f"名称: {artifact.material_name}")
            if artifact.rarity is not None:
                lines.append(f"星级: {artifact.rarity}★")
            return lines

        if artifact.set_name:
            lines.append(f"套装: {artifact.set_name}")
        if artifact.piece_name:
            lines.append(f"名称: {artifact.piece_name}")
        if artifact.piece_type:
            lines.append(f"部位: {artifact.piece_type}")
        if artifact.rarity is not None:
            lines.append(f"星级: {artifact.rarity}★")
        if artifact.level is not None:
            lines.append(f"等级: +{artifact.level}")
        if artifact.main_stat:
            ms = artifact.main_stat
            pct = "%" if ms.is_percentage else ""
            lines.append(f"主词条: {ms.name} +{ms.value}{pct}")
        if artifact.sub_stats:
            lines.append("副词条:")
            for ss in artifact.sub_stats:
                pct = "%" if ss.is_percentage else ""
                lock = " (待激活)" if ss.is_locked else ""
                lines.append(f"  • {ss.name} +{ss.value}{pct}{lock}")
        else:
            lines.append("副词条: 未识别")
        return lines

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

    # ========== 尾锚点动态定位（基于滑块位置） ==========

    @Slot(int)
    def _on_smart_scroll_final_slider_y(self, slider_y: int) -> None:
        """智能拖拽完成后，根据滑块最终位置动态计算尾锚点坐标"""
        tail = self._find_tail_anchor(slider_y)
        if tail is None:
            log.warning("尾锚点定位: 未能找到最后一个物品")
            return
        self._anchor_tail_x, self._anchor_tail_y = tail
        self._anchor_last_x = tail[0]
        self._anchor_last_y = tail[1]
        self.anchorLastFound.emit()
        self._calculate_anchor_pages()

    def _find_tail_anchor(self, slider_y: int) -> tuple[int, int] | None:
        """根据滑块 Y 坐标定位最后一个物品的格子中心

        slider_y: 滑块在窗口中的 Y 坐标（顶部边缘）
        返回: (tail_cx, tail_cy) 窗口相对坐标，或 None
        """
        if self._anchor_first_x == 0 and self._anchor_first_y == 0:
            log.warning("尾锚点定位: 首锚点未标记")
            return None

        # 最后一行物品图标底部 = 滑块顶部 - 30px
        tail_row_bottom = slider_y - 30

        item_h = self._anchor_first_h
        item_w = self._anchor_first_w
        gap = self._grid_gap
        first_y = self._anchor_first_y
        first_x = self._anchor_first_x

        # 当前页面每行的底部 Y 坐标
        rows_bottom = [
            first_y + (gap + item_h) * r + item_h
            for r in range(4)
        ]
        # 找到最接近 tail_row_bottom 的行
        best_row = min(
            range(4),
            key=lambda r: abs(rows_bottom[r] - tail_row_bottom),
        )
        row_bottom = rows_bottom[best_row]

        log.info(
            f"尾锚点定位: slider_y={slider_y}, "
            f"tail_row_bottom={tail_row_bottom}, 匹配行{best_row} "
            f"(row_bottom={row_bottom})"
        )

        # 截图用于空位检测
        result = self._capture.capture()
        if result is None:
            log.warning("尾锚点定位: 截图失败")
            return None

        # 从右向左扫描该行，找到第一个非空格子
        for col in range(7, -1, -1):
            cx = first_x + (gap + item_w) * col + item_w // 2
            cy = row_bottom - item_h // 2

            if not self._is_empty_slot(cx, cy, result):
                log.info(
                    f"尾锚点找到: 行{best_row}, 列{col}, "
                    f"坐标({cx}, {cy})"
                )
                return (cx, cy)

        log.warning("尾锚点定位: 最后一行所有格子均为空")
        return None

    @staticmethod
    def _is_empty_slot(
        cx: int, cy: int, capture_result,
    ) -> bool:
        """检测格子是否为空位（无物品）

        cx, cy: 格子中心坐标（窗口相对）
        capture_result: ScreenshotCapture 的截图结果
        """
        img = capture_result.image
        h, w = img.shape[:2]
        half = 10
        x1 = max(0, cx - half)
        y1 = max(0, cy - half)
        x2 = min(w, cx + half)
        y2 = min(h, cy + half)

        if x2 <= x1 or y2 <= y1:
            return True

        roi = img[y1:y2, x1:x2]
        gray = cv2.cvtColor(roi, cv2.COLOR_RGB2GRAY) if roi.ndim == 3 else roi
        mean_val = np.mean(gray)
        std_val = np.std(gray)
        # 空格子：灰度低且均匀；有物品：灰度高或有纹理变化
        return bool(mean_val < 60 and std_val < 15)

    # ========== 滚动条拖拽 ==========



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
        """智能拖拽到底：检测顶部 → 拖拽 → 检测底部 → 完成。"""
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

        # Step 1: 确保在顶部（双向搜索滑块 → 不在顶部则闯关拖拽到顶）
        slider_y, best_ratio, best_y, _ = self._find_slider(
            result.image, region_x, top_y, bottom_y, bottom_w, bottom_h
        )
        self._emit_slider_debug(
            result.image, region_x, top_y, bottom_y,
            bottom_w, bottom_h, slider_y, "初始检测", best_ratio, best_y,
        )
        if slider_y is None:
            log.warning("智能拖拽到底: 未检测到滑块")
            return

        distance_from_top = slider_y - top_y
        if distance_from_top > self._BOTTOM_PROXIMITY:
            log.info(
                f"智能拖拽到底: 滑块距顶部{distance_from_top}px, 开始闯关拖拽到顶..."
            )
            slider_y = self._scroll_verify_top(
                region_x, top_y, bottom_y, bottom_w, bottom_h, slider_y
            )

        log.info(f"智能拖拽到底: 已确认在顶部 (slider_y={slider_y})")

        # Step 2-4: 灰度搜索底部滑块 → 拖拽 → 停止判定
        log.info(
            f"智能拖拽到底: slider_y={slider_y}, "
            f"region=({region_x},{bottom_y},{bottom_w}x{bottom_h})"
        )

        window = self._capture.find_genshin_window()
        window_bottom = (oy + window.height) if window else (oy + 1000)

        self._scroll_to_bottom_worker = _SmartScrollToBottomWorker(
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

    # ========== 颜色检测到底 ==========

    # 目标灰度值（滑块有两种状态：
    #   不hover: #C7C7C7/#C6C6C6 → 灰度 199/198
    #   hover/点击: #E2E2E2 → 灰度 226
    # 拖拽时鼠标在滑轨附近必触发hover，需同时匹配两种颜色）
    _BOTTOM_TARGET_GRAY: tuple[int, ...] = (198, 199, 226)
    _BOTTOM_GRAY_THRESHOLD: int = 15  # 灰度绝对值差阈值
    _BOTTOM_MATCH_RATIO: float = 0.5  # 采样点匹配比例阈值
    _BOTTOM_EXTRA_TICKS: int = 10  # 确认到底后追加滚动次数
    _BOTTOM_SEARCH_STEP: int = 5  # 向上搜索步长（像素）
    _BOTTOM_MAX_SEARCH: int = 800  # 最大向上搜索距离
    _BOTTOM_PROXIMITY: int = 30  # 判定到底的像素距离阈值
    _BOTTOM_TRACK_GRAY: int = 169  # 滑轨颜色 #A9A9A9 的灰度值
    _BOTTOM_VERIFY_MAX_ATTEMPTS: int = 15  # 闯关验证最大尝试次数
    _BOTTOM_DRAG_DISTANCE: int = 80  # 每次拖拽滑块的距离（像素）
    _BOTTOM_DRAG_STEPS: int = 8  # 拖拽分步数
    _BOTTOM_DRAG_STEP_DELAY: int = 15  # 拖拽每步延迟（ms）
    _BOTTOM_TOP_REGION_Y: int = 184  # 顶部检测起始Y
    _BOTTOM_TOP_REGION_W: int = 7
    _BOTTOM_TOP_REGION_H: int = 23

    @Slot(int, int, int, int)
    def checkScrollBottomByColor(
        self, region_x: int, region_y: int, region_w: int, region_h: int
    ) -> None:
        """颜色检测是否到底：截取检测区域，采样中心点及附近像素颜色，
        与目标颜色对比判断滚动条是否已经到底部。
        如果匹配则追加少量滚动确保 100% 到底。
        """
        result = self._capture.capture()
        if result is None:
            log.warning("颜色检测: 截图失败")
            return

        img = result.image
        slider_y, best_ratio, best_y, _ = self._find_slider(
            img, region_x,
            max(0, region_y - self._BOTTOM_MAX_SEARCH),
            region_y, region_w, region_h,
        )

        # ——— 生成调试预览图 ———
        self._emit_slider_debug(
            img, region_x,
            max(0, region_y - self._BOTTOM_MAX_SEARCH),
            region_y, region_w, region_h, slider_y, "颜色检测",
            best_ratio, best_y,
        )

        if slider_y is None:
            log.warning("颜色检测: 未找到滑块颜色")
            return

        distance_from_bottom = region_y - slider_y

        if distance_from_bottom <= self._BOTTOM_PROXIMITY:
            # 疑似到底 → 闯关验证：滚动并观察滑块是否停止移动
            log.info(
                f"颜色检测: 滑块接近底部 y={slider_y}, 距起始={distance_from_bottom}px, "
                f"开始闯关验证..."
            )
            slider_y = self._scroll_verify_bottom(
                region_x, region_y, region_w, region_h, slider_y
            )
            if slider_y is None:
                log.warning("颜色检测: 闯关验证超时，未确认到底")
                return

            log.info("颜色检测: 闯关验证通过 (滑块已停止), 判定: 已到底 ✓")
            log.info(f"追加{self._BOTTOM_EXTRA_TICKS}次滚动确保100%到底")

            ox, oy = self._window_origin()
            if ox != 0 or oy != 0:
                abs_x = ox + region_x + region_w // 2
                abs_y = oy + region_y + region_h // 2
                self._mouse.move_to(abs_x, abs_y)
                from time import sleep

                for _ in range(self._BOTTOM_EXTRA_TICKS):
                    self._mouse.scroll_one_tick()
                    sleep(0.03)

            log.info("颜色检测: 已确认到底，追加滚动完成")
        else:
            log.info(
                f"颜色检测: 滑块位于 y={slider_y}, 距起始={distance_from_bottom}px, "
                f"判定: 未到底 ✗"
            )

    @staticmethod
    def _find_slider(
        img: np.ndarray,
        region_x: int,
        top_y: int,
        bottom_y: int,
        region_w: int,
        region_h: int,
    ) -> tuple[int | None, float, int, list[int]]:
        """双向查找滑块位置：从顶部向下 + 从底部向上，取最佳匹配。

        无论滑块在滑轨的什么位置，双向搜索都能精准定位。

        Returns:
            (slider_y, best_ratio, best_y, best_samples)
            slider_y — 匹配到的滑块Y坐标，未匹配返回None
            best_ratio — 最佳匹配率（即使未达阈值）
            best_y — 最佳匹配Y坐标（即使未达阈值，-1表示无采样）
            best_samples — 最佳匹配位置的灰度采样值
        """
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        ih, iw = gray.shape

        best_ratio = 0.0
        best_y = -1
        best_samples: list[int] = []

        # 向下搜索：从 top_y 开始
        max_y = min(
            ih - region_h,
            top_y + ArtifactScanPresenter._BOTTOM_MAX_SEARCH,
        )
        for check_y in range(
            top_y, max_y + 1, ArtifactScanPresenter._BOTTOM_SEARCH_STEP
        ):
            ratio, samples = ArtifactScanPresenter._eval_slider_roi(
                gray, region_x, check_y, region_w, region_h
            )
            if ratio > best_ratio:
                best_ratio = ratio
                best_y = check_y
                best_samples = samples
            if ratio >= ArtifactScanPresenter._BOTTOM_MATCH_RATIO:
                return (check_y, best_ratio, best_y, best_samples)

        # 向上搜索：从 bottom_y 开始
        min_y = max(
            0, bottom_y - ArtifactScanPresenter._BOTTOM_MAX_SEARCH
        )
        for check_y in range(
            bottom_y, min_y - 1, -ArtifactScanPresenter._BOTTOM_SEARCH_STEP
        ):
            ratio, samples = ArtifactScanPresenter._eval_slider_roi(
                gray, region_x, check_y, region_w, region_h
            )
            if ratio > best_ratio:
                best_ratio = ratio
                best_y = check_y
                best_samples = samples
            if ratio >= ArtifactScanPresenter._BOTTOM_MATCH_RATIO:
                return (check_y, best_ratio, best_y, best_samples)

        log.warning(
            f"双向搜索未匹配: img={iw}x{ih}, "
            f"top=({region_x},{top_y}), bottom=({region_x},{bottom_y}), "
            f"region=({region_w}x{region_h}), "
            f"最佳匹配率={best_ratio:.2f}@y={best_y}, 灰度值={best_samples}"
        )
        return (None, best_ratio, best_y, best_samples)

    @staticmethod
    def _eval_slider_roi(
        gray: np.ndarray,
        rx: int,
        ry: int,
        rw: int,
        rh: int,
    ) -> tuple[float, list[int]]:
        """评估指定ROI是否匹配滑块颜色。

        Returns:
            (匹配率, 采样灰度值列表)
        """
        roi = gray[ry : ry + rh, rx : rx + rw]
        cx, cy = rw // 2, rh // 2

        samples: list[int] = []
        for dy in range(-1, 2):
            for dx in range(-1, 2):
                py, px = cy + dy, cx + dx
                if 0 <= py < rh and 0 <= px < rw:
                    samples.append(int(roi[py, px]))

        if not samples:
            return (0.0, [])

        match_count = 0
        for sv in samples:
            for tv in ArtifactScanPresenter._BOTTOM_TARGET_GRAY:
                if (
                    abs(sv - tv)
                    < ArtifactScanPresenter._BOTTOM_GRAY_THRESHOLD
                ):
                    match_count += 1
                    break

        return (match_count / len(samples), samples)

    def _scroll_verify_bottom(
        self,
        region_x: int,
        region_y: int,
        region_w: int,
        region_h: int,
        initial_slider_y: int,
    ) -> int | None:
        """闯关验证：滚动并观察滑块是否停止移动。

        滑块停止移动 → 碰到滑轨墙壁 → 确认到底，返回最终滑块Y。
        滑块持续移动 → 还有距离 → 返回 None。
        滑块消失且检测到滑轨颜色 → 到底 → 返回上一次滑块Y。
        """
        prev_y = initial_slider_y

        self.focusGame()
        ox, oy = self._window_origin()
        drag_x = ox + region_x + region_w // 2

        window = self._capture.find_genshin_window()
        window_bottom = (oy + window.height) if window else (oy + 1000)

        log.info(
            f"颜色检测: 闯关开始, 初始滑块Y={prev_y}, "
            f"拖拽列X={drag_x}"
        )

        for attempt in range(self._BOTTOM_VERIFY_MAX_ATTEMPTS):
            # 用 drag 直接拖拽滑块向下（比滚轮可靠）
            drag_from_y = oy + prev_y + region_h // 2
            drag_to_y = min(
                drag_from_y + self._BOTTOM_DRAG_DISTANCE,
                window_bottom - 10,
            )
            self._mouse.drag(
                drag_x, drag_from_y,
                drag_x, drag_to_y,
                self._BOTTOM_DRAG_STEPS,
                self._BOTTOM_DRAG_STEP_DELAY,
            )
            from time import sleep
            sleep(0.15)

            result = self._capture.capture()
            if result is None:
                continue

            img = result.image
            current_y, best_ratio, best_y, _ = self._find_slider(
                img, region_x,
                max(0, region_y - self._BOTTOM_MAX_SEARCH),
                region_y, region_w, region_h,
            )
            self._emit_slider_debug(
                img, region_x,
                max(0, region_y - self._BOTTOM_MAX_SEARCH),
                region_y, region_w, region_h, current_y, f"到底-{attempt + 1}",
                best_ratio, best_y,
            )

            if current_y is None:
                # 滑块消失 → 检查是否看到滑轨颜色
                if self._check_track_color(img, region_x, region_y, region_w, region_h):
                    log.info(f"颜色检测: 闯关第{attempt + 1}次 检测到滑轨颜色, 确认到底")
                    return prev_y
                continue

            if abs(current_y - prev_y) <= 5:
                log.info(
                    f"颜色检测: 闯关第{attempt + 1}次 滑块未移动 "
                    f"(prev={prev_y}, cur={current_y}), 确认到底"
                )
                return current_y

            log.info(
                f"颜色检测: 闯关第{attempt + 1}次 滑块移动 "
                f"(prev={prev_y} → cur={current_y}), 继续..."
            )
            prev_y = current_y

        return None

    def _scroll_verify_top(
        self,
        region_x: int,
        top_y: int,
        bottom_y: int,
        region_w: int,
        region_h: int,
        initial_slider_y: int,
    ) -> int | None:
        """拖拽滑块向上直到撞到顶部滑轨墙壁。

        使用双向搜索 _find_slider 定位滑块，与底部闯关验证一致。
        滑块停止移动 → 碰到滑轨墙壁 → 确认到顶，追加拖拽确保 100%。
        """
        prev_y = initial_slider_y

        self.focusGame()
        ox, oy = self._window_origin()
        drag_x = ox + region_x + region_w // 2

        log.info(
            f"拖拽到顶: 开始, 初始滑块Y={prev_y}, 拖拽列X={drag_x}"
        )

        for attempt in range(self._BOTTOM_VERIFY_MAX_ATTEMPTS):
            drag_from_y = oy + prev_y + region_h // 2
            drag_to_y = max(drag_from_y - self._BOTTOM_DRAG_DISTANCE, oy + 10)
            self._mouse.drag(
                drag_x, drag_from_y,
                drag_x, drag_to_y,
                self._BOTTOM_DRAG_STEPS,
                self._BOTTOM_DRAG_STEP_DELAY,
            )
            from time import sleep
            sleep(0.15)

            result = self._capture.capture()
            if result is None:
                continue

            current_y, best_ratio, best_y, _ = self._find_slider(
                result.image, region_x, top_y, bottom_y, region_w, region_h
            )
            self._emit_slider_debug(
                result.image, region_x, top_y, bottom_y,
                region_w, region_h, current_y, f"到顶-{attempt + 1}",
                best_ratio, best_y,
            )

            if current_y is None:
                log.info(
                    f"拖拽到顶: 第{attempt + 1}次 未找到滑块（可能在顶部边缘），确认到顶"
                )
                break

            if current_y - top_y <= self._BOTTOM_PROXIMITY:
                log.info(
                    f"拖拽到顶: 第{attempt + 1}次 滑块已接近顶部 "
                    f"(y={current_y}, 距顶={current_y - top_y}px), 确认到顶"
                )
                prev_y = current_y
                break

            if abs(current_y - prev_y) <= 5:
                log.info(
                    f"拖拽到顶: 第{attempt + 1}次 滑块未移动 "
                    f"(prev={prev_y}, cur={current_y}), 确认到顶"
                )
                prev_y = current_y
                break

            log.info(
                f"拖拽到顶: 第{attempt + 1}次 滑块移动 "
                f"(prev={prev_y} → cur={current_y}), 继续..."
            )
            prev_y = current_y

        # 追加拖拽确保 100% 到顶
        log.info(f"拖拽到顶: 追加{self._BOTTOM_EXTRA_TICKS}次拖拽确保100%到顶")
        for i in range(self._BOTTOM_EXTRA_TICKS):
            drag_from_y = oy + prev_y + region_h // 2
            drag_to_y = max(
                drag_from_y - self._BOTTOM_DRAG_DISTANCE // 2,
                oy + 10,
            )
            self._mouse.drag(
                drag_x, drag_from_y,
                drag_x, drag_to_y,
                self._BOTTOM_DRAG_STEPS // 2,
                self._BOTTOM_DRAG_STEP_DELAY,
            )
            from time import sleep
            sleep(0.05)

        log.info("拖拽到顶: 完成")
        return prev_y

    def _check_track_color(
        self,
        img: np.ndarray,
        region_x: int,
        region_y: int,
        region_w: int,
        region_h: int,
    ) -> bool:
        """检查区域是否显示滑轨颜色（#A9A9A9 → 灰度 169）"""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        roi = gray[region_y : region_y + region_h, region_x : region_x + region_w]

        cx, cy = region_w // 2, region_h // 2
        samples: list[int] = []
        for dy in range(-1, 2):
            for dx in range(-1, 2):
                py, px = cy + dy, cx + dx
                if 0 <= py < region_h and 0 <= px < region_w:
                    samples.append(int(roi[py, px]))

        if not samples:
            return False

        match_count = sum(
            1 for s in samples
            if abs(s - self._BOTTOM_TRACK_GRAY) < self._BOTTOM_GRAY_THRESHOLD
        )
        return match_count / len(samples) >= self._BOTTOM_MATCH_RATIO

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
        """生成灰度调试预览图：标注双向搜索路径、步进采样点、ROI、滑块位置。

        每次灰度匹配（_find_slider）后调用，实时显示搜索状态。
        """
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        debug = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        ih = gray.shape[0]

        search_x = region_x + region_w // 2
        step = self._BOTTOM_SEARCH_STEP

        # === 向下搜索 ===
        down_end = min(ih - 1, top_y + self._BOTTOM_MAX_SEARCH)
        # 搜索线（绿色）
        cv2.line(debug, (search_x, top_y), (search_x, down_end), (0, 255, 0), 1)
        # 顶部 ROI 框（绿色）
        cv2.rectangle(
            debug, (region_x, top_y),
            (region_x + region_w, top_y + region_h), (0, 255, 0), 1,
        )
        # 步进采样点（小绿点）
        for check_y in range(top_y, down_end + 1, step):
            cv2.circle(debug, (search_x, check_y), 1, (0, 180, 0), -1)

        # === 向上搜索 ===
        up_end = max(0, bottom_y - self._BOTTOM_MAX_SEARCH)
        # 搜索线（绿色）
        cv2.line(debug, (search_x, bottom_y), (search_x, up_end), (0, 255, 0), 1)
        # 底部 ROI 框（绿色）
        cv2.rectangle(
            debug, (region_x, bottom_y),
            (region_x + region_w, bottom_y + region_h), (0, 255, 0), 1,
        )
        # 步进采样点（小绿点）
        for check_y in range(bottom_y, up_end - 1, -step):
            cv2.circle(debug, (search_x, check_y), 1, (0, 180, 0), -1)

        # === 最佳匹配位置（黄色标记，即使未达阈值） ===
        if best_y >= 0:
            cv2.circle(debug, (search_x, best_y), 4, (0, 220, 220), -1)
            cv2.circle(debug, (search_x, best_y), 5, (0, 220, 220), 1)
            cv2.rectangle(
                debug, (region_x, best_y),
                (region_x + region_w, best_y + region_h), (0, 220, 220), 1,
            )
            cv2.putText(
                debug, f"best {best_ratio:.2f}@y={best_y}",
                (region_x + region_w + 4, best_y + region_h // 2),
                cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 220, 220), 1,
            )

        # === 匹配到的滑块（红色实线框） ===
        if slider_y is not None:
            cv2.rectangle(
                debug, (region_x, slider_y),
                (region_x + region_w, slider_y + region_h), (0, 0, 255), 2,
            )
            text = f"slider y={slider_y}"
            if label:
                text = f"[{label}] {text}"
            cv2.putText(
                debug, text,
                (region_x + region_w + 4, slider_y + region_h // 2),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1,
            )

        debug_rgb = cv2.cvtColor(debug, cv2.COLOR_BGR2RGB)
        key = "slider_debug"
        PreviewImageProvider.put(key, debug_rgb)
        self.debugPreviewReady.emit(key)

    @Slot()
    def captureGrayscalePreview(self) -> None:
        """截图并以灰度图显示在预览窗口中（独立于滑块检测，用于调试颜色）"""
        result = self._capture.capture()
        if result is None:
            log.warning("灰度截图: 无法捕获原神窗口")
            return
        gray = cv2.cvtColor(result.image, cv2.COLOR_BGR2GRAY)
        debug = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        debug_rgb = cv2.cvtColor(debug, cv2.COLOR_BGR2RGB)
        key = "grayscale_snapshot"
        PreviewImageProvider.put(key, debug_rgb)
        self.debugPreviewReady.emit(key)
        log.info(
            f"灰度截图: {result.image.shape[1]}x{result.image.shape[0]}"
        )

    def _onScrollToBottomProgress(self, count: int) -> None:
        log.info(f"智能拖拽到底: 已拖拽 {count} 次")

    def _onScrollToBottomFinished(self) -> None:
        self._anchor_scroll_running = False
        self.anchorScrollRunningChanged.emit()
        log.info("智能拖拽到底完成")
        self.scrollbarDragFinished.emit()