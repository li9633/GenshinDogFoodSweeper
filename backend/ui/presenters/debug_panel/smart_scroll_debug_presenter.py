"""
SmartScroll 调试 Presenter
==========================
独立的 SmartScroll 调试面板 Presenter，聚焦于：
- 校准（测量行高 → 校准 px/tick）
- 翻行（指定行数滚动）
- 重置状态

所有阻塞操作（截图、检测、滚动）均分发到后台 QThread 执行，
不阻塞 UI 线程。

与 ArtifactScanDebugPresenter 完全解耦。
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Property, QObject, QThread, Signal, Slot
from ui.lifecycle import OnWindowReady
from utils.logger import log

from backend.automation.mouse_controller import MouseController
from backend.automation.slider_scroller import SliderScroller
from backend.automation.slot_detector import (
    BAG_SLOT_CONFIG,
    SlotDetector,
)
from backend.automation.smart_scroller import SmartScroller
from backend.automation.window_helper import WindowHelper
from backend.exceptions.automation import GameWindowNotFoundError
from backend.utils.screen_capture import ScreenshotCapture

from ..image_provider import PreviewImageProvider


class _DebugWorker(QThread):
    """通用调试后台线程，执行阻塞任务后通过 done/failed 信号通知结果。"""

    done = Signal(object)
    failed = Signal(str)

    def __init__(self, task: Callable[[], object], parent: QObject | None = None):
        super().__init__(parent)
        self._task = task

    def run(self) -> None:
        try:
            result = self._task()
            self.done.emit(result)
        except Exception as e:
            self.failed.emit(str(e))


class SmartScrollDebugPresenter(QObject, OnWindowReady):
    """SmartScroll 调试 — 注册为 QML context property `SmartScrollDebug`"""

    smartCalibratedChanged = Signal()
    smartPixelsPerScrollChanged = Signal()
    debugPreviewReady = Signal(str)

    def __init__(self, parent: QObject | None = None):
        QObject.__init__(self, parent)
        OnWindowReady.__init__(self)
        self._mouse = MouseController()

    def on_window_ready(self) -> None:
        self._capture = ScreenshotCapture()
        self._active_config = BAG_SLOT_CONFIG
        self._slider_scroller = SliderScroller(
            self._mouse,
            self._capture,
            self._active_config,
        )
        self._smart_scroller: SmartScroller | None = None

    def _get_smart_scroller(self) -> SmartScroller:
        if self._smart_scroller is None:
            self._smart_scroller = SmartScroller(
                self._capture,
                self._mouse,
                slider=self._slider_scroller,
                config=self._active_config,
            )
        return self._smart_scroller

    def _run_in_background(self, task: Callable[[], object]) -> _DebugWorker:
        worker = _DebugWorker(task, parent=self)
        worker.failed.connect(
            lambda e: log.warning(f"[SmartScroll调试] 后台任务失败: {e}")
        )
        worker.start()
        return worker

    @Property(bool, notify=smartCalibratedChanged)
    def smartCalibrated(self) -> bool:
        return self._smart_scroller.is_calibrated if self._smart_scroller else False

    @Property(float, notify=smartPixelsPerScrollChanged)
    def smartPixelsPerScroll(self) -> float:
        return self._smart_scroller.pixels_per_scroll if self._smart_scroller else 0.0

    @Property(int, notify=smartPixelsPerScrollChanged)
    def smartCurrentRow(self) -> int:
        return self._smart_scroller.current_row if self._smart_scroller else 0

    @Slot()
    def smartCalibrate(self) -> None:
        def _task() -> object:
            sc = self._get_smart_scroller()
            sc.calibrate()
            return None

        def _on_done(_: object) -> None:
            self.smartCalibratedChanged.emit()
            self.smartPixelsPerScrollChanged.emit()
            log.info("[SmartScroll调试] 校准完成")

        self._run_in_background(_task).done.connect(_on_done)

    @Slot()
    def smartScrollToTop(self) -> None:
        def _task() -> object:
            sc = self._get_smart_scroller()
            sc.scroll_to_top()
            return None

        def _on_done(_: object) -> None:
            self.smartPixelsPerScrollChanged.emit()
            log.info("[SmartScroll调试] 已滚动到顶")

        self._run_in_background(_task).done.connect(_on_done)

    @Slot(int)
    def smartScrollRows(self, rows: int) -> None:
        def _task() -> object:
            sc = self._get_smart_scroller()
            sc.scroll_rows(rows)
            return rows

        def _on_done(result: object) -> None:
            self.smartPixelsPerScrollChanged.emit()
            log.info(f"[SmartScroll调试] 翻行: {result}")

        self._run_in_background(_task).done.connect(_on_done)

    @Slot()
    def smartReset(self) -> None:
        if self._smart_scroller:
            self._smart_scroller.reset()
            self.smartPixelsPerScrollChanged.emit()
            log.info("[SmartScroll调试] 状态已重置")

    @Slot()
    def smartMeasureRowHeight(self) -> None:
        def _task() -> object:
            window = WindowHelper.find_genshin_window()
            result = self._capture.capture(window=window)
            if result is None:
                raise GameWindowNotFoundError()
            det = SlotDetector.detect(result.image, config=self._active_config)
            if det.row_height <= 0:
                return None
            sc = self._get_smart_scroller()
            sc._row_height = det.row_height
            debug_rgb = SlotDetector.generate_row_height_debug(
                result.image,
                det,
                config=self._active_config,
            )
            vkey = PreviewImageProvider.put("smart_scroll", debug_rgb)
            return {"vkey": vkey, "row_height": det.row_height}

        def _on_done(result: object) -> None:
            if result is None:
                log.warning("[SmartScroll调试] 行高测量: 未检测到格子")
                return
            self.debugPreviewReady.emit(result["vkey"])
            log.info(f"[SmartScroll调试] 行高已更新: {result['row_height']}px")

        self._run_in_background(_task).done.connect(_on_done)