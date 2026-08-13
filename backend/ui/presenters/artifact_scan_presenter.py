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
from backend.automation.template_manager import TemplateManager
from backend.automation.template_matcher import find_all_matches, multi_scale_match
from backend.utils.screen_capture import ScreenshotCapture


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


class _ScrollToBottomWorker(QThread):
    """后台线程：快速滚动到底部"""

    progress = Signal(int, int)  # (current_tick, total_ticks)
    finished = Signal()

    def __init__(
        self,
        mouse: MouseController,
        origin_x: int,
        origin_y: int,
        flag_x: int,
        flag_y: int,
        total_ticks: int,
        tick_delay_ms: int,
    ):
        super().__init__()
        self._mouse = mouse
        self._origin_x = origin_x
        self._origin_y = origin_y
        self._flag_x = flag_x
        self._flag_y = flag_y
        self._total_ticks = total_ticks
        self._tick_delay_ms = tick_delay_ms
        self._stop = False

    def stop(self) -> None:
        self._stop = True

    def run(self) -> None:
        from time import sleep

        for i in range(1, self._total_ticks + 1):
            if self._stop:
                break
            self._mouse.move_to(
                self._origin_x + self._flag_x,
                self._origin_y + self._flag_y,
            )
            self._mouse.scroll_one_tick()
            self.progress.emit(i, self._total_ticks)
            sleep(self._tick_delay_ms / 1000.0)

        self.finished.emit()


class _SmartScrollToBottomWorker(QThread):
    """智能滚轮到底部：快速滚轮 + 周期性截图检测滑块位置"""

    TICKS_PER_BATCH = 20
    CHECK_INTERVAL_BATCHES = 2  # 每 N 批检测一次

    progress = Signal(int)  # 已滚格数
    finished = Signal()

    def __init__(
        self,
        mouse: MouseController,
        scroll_x: int,
        scroll_y: int,
        capture: ScreenshotCapture,
        target_thumb_y: int,
        tick_delay_ms: int = 20,
    ):
        super().__init__()
        self._mouse = mouse
        self._scroll_x = scroll_x
        self._scroll_y = scroll_y
        self._capture = capture
        self._target_thumb_y = target_thumb_y
        self._tick_delay_ms = tick_delay_ms
        self._stop = False

    def stop(self) -> None:
        self._stop = True

    def run(self) -> None:
        from time import sleep

        total_ticks = 0
        batch_count = 0

        while not self._stop:
            # 滚一批
            self._mouse.move_to(self._scroll_x, self._scroll_y)
            for _ in range(self.TICKS_PER_BATCH):
                if self._stop:
                    break
                self._mouse.scroll_one_tick()
                total_ticks += 1
                sleep(self._tick_delay_ms / 1000.0)

            if self._stop:
                break

            self.progress.emit(total_ticks)
            batch_count += 1

            # 每 N 批检测一次滑块位置
            if batch_count % self.CHECK_INTERVAL_BATCHES == 0:
                sleep(0.15)  # 等 UI 稳定
                result = self._capture.capture()
                if result is not None:
                    pos = ArtifactScanPresenter._find_scrollbar_thumb(result.image)
                    if pos is not None:
                        current_thumb_y = pos[1]
                        if current_thumb_y >= self._target_thumb_y - 10:
                            log.info(
                                f"智能滚轮: 滑块已到达目标位置 "
                                f"(current={current_thumb_y}, target={self._target_thumb_y})"
                            )
                            break

        # 安全追加
        if not self._stop:
            for _ in range(5):
                self._mouse.scroll_one_tick()
                total_ticks += 1
                sleep(0.03)

        self.progress.emit(total_ticks)
        self.finished.emit()


class ArtifactScanPresenter(QObject):
    """圣遗物扫描 — 注册为 QML context property

    QML 传入的坐标是相对于原神窗口左上角的偏移，
    内部自动转换为屏幕绝对坐标后调用 MouseController。
    """

    clickResultChanged = Signal()
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
    anchorScrollProgressChanged = Signal()
    scrollbarDragFinished = Signal()
    scrollbarTrackHeightChanged = Signal()

    # 翻页
    SCROLL_TICKS_PER_ROW = 10
    ARTIFACTS_PER_PAGE = 32  # 4 行 × 8 列

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._mouse = MouseController()
        self._capture = ScreenshotCapture()
        self._last_result = ""
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
        self._anchor_total_pages = 0
        self._anchor_total_rows = 0
        self._anchor_scroll_worker: _ScrollToBottomWorker | None = None
        self._anchor_scroll_running = False
        self._anchor_scroll_progress = ""
        self._anchor_first_template: np.ndarray | None = None

        # 智能滚轮到底
        self._scroll_to_bottom_worker: _SmartScrollToBottomWorker | None = None
        self._scrollbar_track_height = 760

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

    @Property(str, notify=clickResultChanged)
    def clickResult(self) -> str:
        return self._last_result

    # ========== 公开 Slot ==========

    @Slot(int, int)
    def moveTo(self, x: int, y: int) -> None:
        ax, ay = self._to_absolute(x, y)
        ok = self._mouse.move_to(ax, ay)
        self._last_result = (
            f"已移动到窗口({x}, {y}) → 屏幕({ax}, {ay})" if ok else "移动失败"
        )
        self.clickResultChanged.emit()
        log.info(
            f"鼠标移动: 窗口({x}, {y}) → 屏幕({ax}, {ay}) {'成功' if ok else '失败'}"
        )

    @Slot(int, int)
    def clickAt(self, x: int, y: int) -> None:
        ax, ay = self._to_absolute(x, y)
        ok = self._mouse.move_and_click(ax, ay)
        self._last_result = (
            f"已点击窗口({x}, {y}) → 屏幕({ax}, {ay})" if ok else "点击失败"
        )
        self.clickResultChanged.emit()
        log.debug(
            f"鼠标点击: 窗口({x}, {y}) → 屏幕({ax}, {ay}) {'成功' if ok else '失败'}"
        )

    @Slot()
    def focusGame(self) -> None:
        hwnd = self._genshin_hwnd()
        if hwnd is None:
            self._last_result = "未检测到原神窗口"
            self.clickResultChanged.emit()
            return
        ok = self._mouse.focus_window(hwnd)
        self._last_result = "原神窗口已聚焦" if ok else "聚焦失败"
        self.clickResultChanged.emit()
        log.info(f"聚焦原神窗口: {'成功' if ok else '失败'}")

    @Slot(int, int)
    def moveAndClick(self, x: int, y: int) -> None:
        self.clickAt(x, y)

    @Slot(int)
    def scrollWheel(self, clicks: int) -> None:
        ok = self._mouse.scroll(clicks)
        self._last_result = f"滚轮 {clicks} 格" if ok else "滚轮失败"
        self.clickResultChanged.emit()
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
            self._last_result = "未检测到原神窗口"
            self.clickResultChanged.emit()
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
        self._last_result = "批量点击完成"
        self.clickResultChanged.emit()
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
            self._last_result = "未检测到原神窗口"
            self.clickResultChanged.emit()
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
        self._last_result = f"翻页完成 (滚了{self._scroll_ticks}格)"
        self.clickResultChanged.emit()
        log.info(f"翻页完成: 滚了{self._scroll_ticks}格")

    @Slot()
    def resetScrollState(self) -> None:
        """重置翻页状态"""
        self._scroll_ticks = 0
        self._scroll_running = False
        self.scrollStateChanged.emit()
        self._last_result = "翻页状态已重置"
        self.clickResultChanged.emit()

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
            self._last_result = "未检测到原神窗口"
            self.clickResultChanged.emit()
            return

        result = self._capture.capture()
        if result is None:
            self._last_result = "截图失败"
            self.clickResultChanged.emit()
            return

        img = result.image
        h, w = img.shape[:2]

        x1 = max(0, roi_x)
        y1 = max(0, roi_y)
        x2 = min(w, roi_x + roi_w)
        y2 = min(h, roi_y + roi_h)

        if x2 <= x1 or y2 <= y1:
            self._last_result = "ROI 区域无效"
            self.clickResultChanged.emit()
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
        self._last_result = "OCR 识别中…"
        self.clickResultChanged.emit()
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

        self._last_result = (
            f"识别到 {count} 个圣遗物，共 {self._detected_total_pages} 页"
        )
        self.clickResultChanged.emit()
        log.info(
            f"OCR 数量识别完成: {count} 个, {self._detected_total_pages} 页"
        )

    def _on_ocr_count_error(self, error: str, _callback_data: object) -> None:
        self._last_result = f"OCR 识别失败: {error}"
        self.clickResultChanged.emit()
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
            self._last_result = "请先 OCR 识别圣遗物数量"
            self.clickResultChanged.emit()
            return

        self.focusGame()

        ox, oy = self._window_origin()
        if ox == 0 and oy == 0:
            self._last_result = "未检测到原神窗口"
            self.clickResultChanged.emit()
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
        self._last_result = "自动翻页完成"
        self.clickResultChanged.emit()
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

    @Property(str, notify=anchorScrollProgressChanged)
    def anchorScrollProgress(self) -> str:
        return self._anchor_scroll_progress

    @Property(int, notify=scrollbarTrackHeightChanged)
    def scrollbarTrackHeight(self) -> int:
        return self._scrollbar_track_height

    @scrollbarTrackHeight.setter
    def scrollbarTrackHeight(self, value: int) -> None:
        if self._scrollbar_track_height != value:
            self._scrollbar_track_height = value
            self.scrollbarTrackHeightChanged.emit()

    @Slot(int, int, int, int)
    def markFirstAnchor(self, x: int, y: int, w: int, h: int) -> None:
        """标记第一个圣遗物（首锚点），保存位置和模板截图"""
        self._anchor_first_x = x
        self._anchor_first_y = y
        self._anchor_first_w = w
        self._anchor_first_h = h

        result = self._capture.capture()
        if result is not None:
            img = result.image
            roi = img[y:y + h, x:x + w].copy()
            self._anchor_first_template = cv2.cvtColor(roi, cv2.COLOR_RGB2GRAY)

        self._anchor_last_x = 0
        self._anchor_last_y = 0
        self._anchor_total_pages = 0
        self._anchor_total_rows = 0
        self.anchorFirstMarked.emit()
        self.anchorLastFound.emit()
        self.anchorPagesCalculated.emit()
        self._last_result = f"首锚点已标记: ({x}, {y}, {w}x{h})"
        self.clickResultChanged.emit()
        log.info(
            f"首锚点已标记: ({x}, {y}, {w}x{h}), "
            f"模板{'已保存' if self._anchor_first_template is not None else '保存失败'}"
        )

    @Slot(int, int, int, int)
    def startScrollToBottom(
        self, flag_x: int, flag_y: int, total_ticks: int, tick_delay_ms: int
    ) -> None:
        """开始快速滚动到底部"""
        if self._anchor_scroll_running:
            return

        self.focusGame()

        ox, oy = self._window_origin()
        if ox == 0 and oy == 0:
            self._last_result = "未检测到原神窗口"
            self.clickResultChanged.emit()
            return

        self._anchor_scroll_worker = _ScrollToBottomWorker(
            mouse=self._mouse,
            origin_x=ox,
            origin_y=oy,
            flag_x=flag_x,
            flag_y=flag_y,
            total_ticks=total_ticks,
            tick_delay_ms=tick_delay_ms,
        )
        self._anchor_scroll_worker.progress.connect(self._on_anchor_scroll_progress)
        self._anchor_scroll_worker.finished.connect(self._on_anchor_scroll_finished)

        self._anchor_scroll_running = True
        self._anchor_scroll_progress = f"0/{total_ticks}"
        self.anchorScrollRunningChanged.emit()
        self.anchorScrollProgressChanged.emit()

        self._anchor_scroll_worker.start()
        log.info(f"快速滚动到底部: 共 {total_ticks} 次, 延迟={tick_delay_ms}ms")

    @Slot()
    def stopScrollToBottom(self) -> None:
        """停止快速滚动"""
        if self._anchor_scroll_worker is not None:
            self._anchor_scroll_worker.stop()
        log.info("快速滚动已停止")

    def _on_anchor_scroll_progress(self, current: int, total: int) -> None:
        self._anchor_scroll_progress = f"{current}/{total}"
        self.anchorScrollProgressChanged.emit()

    def _on_anchor_scroll_finished(self) -> None:
        self._anchor_scroll_running = False
        self._anchor_scroll_worker = None
        self.anchorScrollRunningChanged.emit()
        self._last_result = "已滚到底部，请点击「查找尾锚点」"
        self.clickResultChanged.emit()
        log.info("快速滚动到底部完成")

    @Slot()
    def findLastAnchor(self) -> None:
        """模板匹配查找最后一个圣遗物（尾锚点）"""
        if self._anchor_first_template is None:
            self._last_result = "请先标记首锚点"
            self.clickResultChanged.emit()
            return

        result = self._capture.capture()
        if result is None:
            self._last_result = "截图失败"
            self.clickResultChanged.emit()
            return

        screen_gray = cv2.cvtColor(result.image, cv2.COLOR_RGB2GRAY)
        matches = find_all_matches(screen_gray, self._anchor_first_template, threshold=0.7)

        if not matches:
            self._last_result = "未找到匹配，请手动标记尾锚点"
            self.clickResultChanged.emit()
            self.anchorLastFound.emit()
            log.info("尾锚点查找: 模板匹配未找到结果")
            return

        # 取最底部（Y 最大）的匹配作为尾锚点
        best = matches[-1]
        score, x, y, w, h = best
        self._anchor_last_x = x
        self._anchor_last_y = y
        self.anchorLastFound.emit()
        self._last_result = f"尾锚点已找到: ({x}, {y}) 置信度={score:.2f}"
        self.clickResultChanged.emit()
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
        self._last_result = f"尾锚点已手动标记: ({x}, {y})"
        self.clickResultChanged.emit()
        log.info(f"尾锚点已手动标记: ({x}, {y})")
        self._calculate_anchor_pages()

    def _calculate_anchor_pages(self) -> None:
        """根据首尾锚点计算总页数"""
        if self._anchor_first_y == 0 or self._anchor_last_y == 0:
            return

        row_h = self._anchor_first_h
        if row_h <= 0:
            return

        # 当前屏幕可见的锚点范围
        visible_rows = (self._anchor_last_y - self._anchor_first_y) / row_h
        total_rows = int(visible_rows) + 4  # 加上首锚点所在页的 4 行
        self._anchor_total_rows = total_rows
        self._anchor_total_pages = max(1, (total_rows + 3) // 4)  # 向上取整
        self.anchorPagesCalculated.emit()
        self._last_result = (
            f"锚点计算: {total_rows} 行, {self._anchor_total_pages} 页"
        )
        self.clickResultChanged.emit()
        log.info(
            f"锚点计算: first=({self._anchor_first_x},{self._anchor_first_y}) "
            f"last=({self._anchor_last_x},{self._anchor_last_y}) "
            f"row_h={row_h} → {total_rows} 行, {self._anchor_total_pages} 页"
        )

    # ========== 滚动条拖拽 ==========

    @staticmethod
    def _find_scrollbar_thumb(
        screenshot: np.ndarray,
    ) -> tuple[int, int, int, int, int] | None:
        """通过模板匹配在截图中查找滚动条滑块位置。

        使用「背包滚动条滑块」模板在 region 内匹配当前滑块。
        返回 (thumb_center_x, thumb_center_y, track_bottom, track_width, thumb_height)
        均为截图内坐标，找不到返回 None。
        """
        tmpl_path = TemplateManager.get_path("背包滚动条滑块")
        region = TemplateManager.get_region("背包滚动条滑块")
        if tmpl_path is None or region is None:
            log.warning("背包滚动条滑块模板未配置")
            return None

        tmpl = cv2.imread(str(tmpl_path), cv2.IMREAD_GRAYSCALE)
        if tmpl is None:
            log.warning(f"无法读取滚动条模板: {tmpl_path}")
            return None

        rx, ry, rw, rh = region
        h, w = screenshot.shape[:2]
        if ry + rh > h or rx + rw > w:
            log.warning(
                f"滚动条 region 超出截图范围: "
                f"region=({rx},{ry},{rw}x{rh}), screenshot=({w}x{h})"
            )
            return None

        search_area = screenshot[ry:ry + rh, rx:rx + rw]
        search_gray = cv2.cvtColor(search_area, cv2.COLOR_RGB2GRAY)

        score, (mx, my), _, (tw, th) = multi_scale_match(search_gray, tmpl)
        if score < 0.5:
            log.debug(f"滚动条滑块匹配得分过低: {score:.2f}")
            return None

        thumb_center_x = rx + mx + tw // 2
        thumb_center_y = ry + my + th // 2
        thumb_height = th
        track_bottom = ry + rh

        log.debug(
            f"滚动条滑块: region=({rx},{ry},{rw}x{rh}), "
            f"match=({mx},{my}) score={score:.2f}, "
            f"thumb_center=({thumb_center_x},{thumb_center_y}), "
            f"thumb_h={thumb_height}, track_bottom={track_bottom}"
        )
        return thumb_center_x, thumb_center_y, track_bottom, rw, thumb_height

    @Slot()
    def scrollToBottom(self) -> None:
        """智能滚轮到底部：模板匹配滑块 → 计算目标位置 → 快速滚轮 → 周期性检测滑块位置"""
        if self._scroll_to_bottom_worker is not None and self._scroll_to_bottom_worker.isRunning():
            return

        ox, oy = self._window_origin()
        if ox == 0 and oy == 0:
            self._last_result = "未检测到原神窗口"
            self.clickResultChanged.emit()
            return

        result = self._capture.capture()
        if result is None:
            self._last_result = "截图失败"
            self.clickResultChanged.emit()
            return

        pos = self._find_scrollbar_thumb(result.image)
        if pos is None:
            self._last_result = "未检测到滚动条滑块"
            self.clickResultChanged.emit()
            return

        thumb_center_x, thumb_center_y, _, _, thumb_h = pos
        track_height = self._scrollbar_track_height
        target_thumb_y = thumb_center_y + track_height

        abs_scroll_x = ox + thumb_center_x
        abs_scroll_y = oy + thumb_center_y

        log.info(
            f"智能滚轮到底: thumb_y={thumb_center_y}, thumb_h={thumb_h}, "
            f"track_height={track_height}, target_y={target_thumb_y}"
        )

        self._scroll_to_bottom_worker = _SmartScrollToBottomWorker(
            mouse=self._mouse,
            scroll_x=abs_scroll_x,
            scroll_y=abs_scroll_y,
            capture=self._capture,
            target_thumb_y=target_thumb_y,
            tick_delay_ms=20,
        )
        self._scroll_to_bottom_worker.progress.connect(self._onScrollToBottomProgress)
        self._scroll_to_bottom_worker.finished.connect(self._onScrollToBottomFinished)
        self._scroll_to_bottom_worker.start()
        self._anchor_scroll_running = True
        self.anchorScrollRunningChanged.emit()

    def _onScrollToBottomProgress(self, ticks: int) -> None:
        self._anchor_scroll_progress = f"{ticks} 格"
        self.anchorScrollProgressChanged.emit()

    def _onScrollToBottomFinished(self) -> None:
        self._anchor_scroll_running = False
        self.anchorScrollRunningChanged.emit()
        self._last_result = "已滚动到底部"
        self.clickResultChanged.emit()
        log.info("智能滚轮到底完成")
        self.scrollbarDragFinished.emit()