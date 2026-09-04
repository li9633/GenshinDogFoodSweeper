"""
圣遗物扫描调试 Presenter
=========================
独立的调试面板 Presenter，聚焦于单个小模块的调试：
- 格子定位
- 格子翻页
- 批量点击
- 首尾锚点定位
- 格子检测预览

所有阻塞操作（截图、检测、滚动、OCR）均分发到后台 QThread 执行，
不阻塞 UI 线程。

与主流程 ArtifactScanPresenter 完全解耦，各自独立管理配置和状态。
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from time import sleep

import numpy as np
from models.artifact import ArtifactInfo
from PySide6.QtCore import Property, QObject, QThread, QTimer, Signal, Slot
from ui.lifecycle import OnWindowReady
from utils.logger import log

from backend.automation.anchor_locator import AnchorLocator
from backend.automation.artifact_count_ocr import ocr_artifact_count
from backend.automation.debug_preview import DebugPreview
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
from backend.automation.slot_iterator import SlotIterator
from backend.automation.smart_scroller import SmartScroller
from backend.automation.window_helper import WindowHelper
from backend.exceptions.automation import GameWindowNotFoundError
from backend.models.slot_models import DetectResult
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


class ArtifactScanDebugPresenter(QObject, OnWindowReady):
    """圣遗物扫描调试 — 注册为 QML context property `ArtifactScanDebug`"""

    # ========== 信号 ==========

    batchProgressChanged = Signal()
    batchRunningChanged = Signal()
    anchorFirstMarked = Signal()
    anchorLastFound = Signal()
    anchorPagesCalculated = Signal()
    anchorScrollRunningChanged = Signal()
    scrollbarTrackHeightChanged = Signal()
    debugPreviewReady = Signal(str)
    anchorFirstRecognizedChanged = Signal()
    anchorTailRecognizedChanged = Signal()
    activeConfigChanged = Signal()

    def __init__(self, parent: QObject | None = None):
        QObject.__init__(self, parent)
        OnWindowReady.__init__(self)
        self._mouse = MouseController()

    def on_window_ready(self) -> None:
        self._capture = ScreenshotCapture()

        self._available_configs = ALL_SLOT_CONFIGS
        self._active_config = BAG_SLOT_CONFIG
        self._active_config_index = 0

        self._slider_scroller = SliderScroller(
            self._mouse,
            self._capture,
            self._active_config,
            debug_callback=self._emit_slider_debug,
        )

        self._page_scroller = PageScroller(self._mouse, self._capture)

        # 批量点击
        self._batch_progress = ""
        self._batch_running = False
        self._batch_worker: QThread | None = None
        self._batch_click_interval = 100

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

        self._scrollbar_track_height = 760

        # 锚点OCR识别
        self._anchor_ocr_connected = False
        self._anchor_first_display_text = ""
        self._anchor_tail_display_text = ""
        self._anchor_first_recognized = False
        self._anchor_tail_recognized = False

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
        """将阻塞任务分发到后台线程执行。"""
        worker = _DebugWorker(task, parent=self)
        worker.failed.connect(lambda e: log.warning(f"[调试面板] 后台任务失败: {e}"))
        worker.start()
        return worker

    # ==================================================================
    # 配置管理
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
            self._smart_scroller = None
            log.info(f"[调试面板] 格子检测配置切换: {self._active_config.name}")
            self.activeConfigChanged.emit()

    # ==================================================================
    # 批量点击（基于 SlotIterator）
    # ==================================================================

    @Property(str, notify=batchProgressChanged)
    def batchProgress(self) -> str:
        return self._batch_progress

    @Property(bool, notify=batchRunningChanged)
    def batchRunning(self) -> bool:
        return self._batch_running

    @Slot()
    def startBatchClick(self) -> None:
        if self._batch_running:
            return
        WindowHelper.focus()

        def _task() -> object:
            window = WindowHelper.find_genshin_window()
            result = self._capture.capture(window=window)
            if result is None:
                raise GameWindowNotFoundError()
            det_result = SlotDetector.detect(result.image, config=self._active_config)
            if not det_result.slots:
                return None
            return det_result

        def _on_done(det_result: object) -> None:
            if det_result is None:
                log.warning("[调试面板] 批量点击初始化: 未检测到格子")
                return
            self._batch_running = True
            self.batchRunningChanged.emit()
            self._batch_worker = _SlotClickWorker(
                self._mouse,
                det_result,
                self._batch_click_interval,
            )
            self._batch_worker.progress.connect(self._on_batch_progress)
            self._batch_worker.finished.connect(self._on_batch_finished)
            self._batch_worker.start()

        worker = _DebugWorker(_task, parent=self)
        worker.done.connect(_on_done)
        worker.failed.connect(
            lambda e: log.warning(f"[调试面板] 批量点击初始化失败: {e}")
        )
        worker.start()

    @Slot()
    def stopBatchClick(self) -> None:
        if self._batch_worker is not None:
            self._batch_worker.stop()
            self._batch_worker = None
        self._batch_running = False
        self.batchRunningChanged.emit()

    def _on_batch_progress(self, current: int, total: int) -> None:
        self._batch_progress = f"{current}/{total}"
        self.batchProgressChanged.emit()

    def _on_batch_finished(self) -> None:
        self._batch_running = False
        self._batch_worker = None
        self.batchRunningChanged.emit()
        log.info("[调试面板] 批量点击完成")

    # ==================================================================
    # 格子定位
    # ==================================================================

    @Slot(int, int, int)
    def navigateToSlot(self, page: int, row: int, col: int) -> None:
        def _task() -> object:
            cfg = self._active_config
            roi = cfg.roi
            if roi is None:
                raise ValueError("ROI 未配置")
            rx, ry, rw, rh = roi

            ox, oy = WindowHelper.get_origin()
            MouseController.set_origin((ox, oy))
            WindowHelper.focus()

            sc = self._get_smart_scroller()
            if not sc.scroll_to_top():
                log.warning("[调试面板] 无法滚动到顶")
                return None
            sc.calibrate()
            sc.scroll_to_top(force=True)

            total_rows = page * cfg.rows
            sc.scroll_rows(total_rows)

            window = WindowHelper.find_genshin_window()
            result = self._capture.capture(window=window)
            if result is None:
                raise GameWindowNotFoundError()

            det_result = SlotDetector.detect(result.image, config=cfg)
            if row >= cfg.rows or col >= cfg.cols:
                raise ValueError(f"行列({row},{col})超出范围({cfg.rows}x{cfg.cols})")

            col_lefts, col_rights, row_bottoms, _, _ = SlotDetector._compute_grid(
                (rx, ry, rw, rh), cfg, det_result.bottom_y
            )
            cx = (col_lefts[col] + col_rights[col]) // 2
            cy = row_bottoms[row] - cfg.slot_h // 2
            self._mouse.move_and_click(cx, cy)
            return {"page": page, "row": row, "col": col, "cx": cx, "cy": cy}

        def _on_done(result: object) -> None:
            if result is None:
                log.warning("[调试面板] 定位失败: 无法滚动到顶")
                return
            r = result
            log.info(
                f"[调试面板] 定位完成: P{r['page']}R{r['row']}C{r['col']} → ({r['cx']}, {r['cy']})"
            )

        self._run_in_background(_task).done.connect(_on_done)

    # ==================================================================
    # 格子翻页
    # ==================================================================

    @Slot(int, int, int)
    def scrollPageByDetection(
        self, _flag_x: int, _flag_y: int, scroll_delay_ms: int = 80
    ) -> None:
        def _task() -> object:
            WindowHelper.focus()
            window = WindowHelper.find_genshin_window()
            if window is None:
                raise GameWindowNotFoundError()
            result = self._capture.capture(window=window)
            self._page_scroller.set_config(self._active_config)
            det_result = SlotDetector.detect(result.image, config=self._active_config)
            self._page_scroller.scroll_to_next_page(
                det_result, tick_delay_ms=scroll_delay_ms
            )
            return None

        worker = self._run_in_background(_task)
        worker.done.connect(lambda _: log.info("[调试面板] 格子翻页完成"))

    @Slot(int, int, int)
    def scrollPageToBottom(
        self, _flag_x: int, _flag_y: int, scroll_delay_ms: int = 80
    ) -> None:
        def _task() -> object:
            WindowHelper.focus()
            window = WindowHelper.find_genshin_window()
            if window is None:
                raise GameWindowNotFoundError()
            engines_dir = Path(__file__).resolve().parents[4] / "engines"
            ocr = OcrEngine.create_ocr(engines_dir)
            count = ocr_artifact_count(self._capture, ocr)
            total_pages = max(1, (count + 31) // 32) if count > 0 else 0
            max_pages = total_pages - 1 if total_pages > 0 else 0
            self._page_scroller.set_config(self._active_config)
            pages = self._page_scroller.scroll_to_bottom(
                tick_delay_ms=scroll_delay_ms,
                max_pages=max_pages,
                total_pages=total_pages,
            )
            return {"count": count, "total_pages": total_pages, "pages": pages}

        def _on_done(result: object) -> None:
            r = result
            log.info(
                f"[调试面板] 自动翻到底完成: 数量={r['count']}, "
                f"总页数={r['total_pages']}, 翻页{r['pages']}次"
            )

        self._run_in_background(_task).done.connect(_on_done)

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
        def _task() -> object:
            window = WindowHelper.find_genshin_window()
            result = self._capture.capture(window=window)
            if result is None:
                raise GameWindowNotFoundError()
            cfg = self._active_config
            det_result = SlotDetector.detect(result.image, config=cfg)
            if not det_result.slots:
                return None
            first = det_result.slots[0]
            return {"cx": first.cx, "cy": first.cy, "sx": first.x, "sy": first.y}

        def _on_done(result: object) -> None:
            if result is None:
                log.warning("[调试面板] 首锚点定位: 未检测到格子")
                return
            r = result
            cx, cy, sx, sy = r["cx"], r["cy"], r["sx"], r["sy"]
            self._anchor_first_x = sx
            self._anchor_first_y = sy
            self._anchor_first_display_text = ""
            self._anchor_first_recognized = False
            self.anchorFirstMarked.emit()
            self.anchorFirstRecognizedChanged.emit()
            log.info(f"[调试面板] 首锚点已定位: 第1个格子 ({sx}, {sy})")
            self._recognize_anchor_item(cx, cy, "first")

        self._run_in_background(_task).done.connect(_on_done)

    def _calculate_anchor_pages(self) -> None:
        if self._anchor_first_y == 0 or self._anchor_last_y == 0:
            return
        is_tail_center = self._anchor_tail_y != 0
        rows, pages = AnchorLocator.calculate_pages(
            self._anchor_first_y,
            self._anchor_last_y,
            self._active_config.slot_h,
            24,
            is_tail_center=is_tail_center,
        )
        self._anchor_total_rows = rows
        self._anchor_total_pages = pages
        self.anchorPagesCalculated.emit()
        log.info(
            f"[调试面板] 锚点计算: first=({self._anchor_first_x},{self._anchor_first_y}) "
            f"last=({self._anchor_last_x},{self._anchor_last_y}) → {rows}行, {pages}页"
        )

    @Slot()
    def recognizeLastAnchor(self) -> None:
        def _task() -> object:
            window = WindowHelper.find_genshin_window()
            result = self._capture.capture(window=window)
            if result is None:
                raise GameWindowNotFoundError()
            cfg = self._active_config
            det_result = SlotDetector.detect(result.image, config=cfg)
            if not det_result.slots:
                return None
            last = det_result.slots[-1]
            return {"cx": last.cx, "cy": last.cy, "sx": last.x, "sy": last.y}

        def _on_done(result: object) -> None:
            if result is None:
                log.warning("[调试面板] 尾锚点定位: 未检测到格子")
                return
            r = result
            cx, cy, sx, sy = r["cx"], r["cy"], r["sx"], r["sy"]
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
            log.info(f"[调试面板] 尾锚点已定位: 最后1个格子 ({sx}, {sy})")
            self._recognize_anchor_item(cx, cy, "tail")

        self._run_in_background(_task).done.connect(_on_done)

    def _connect_anchor_ocr_worker(self) -> None:
        if self._anchor_ocr_connected:
            return
        from backend.automation.ocr_worker import OcrWorker

        worker = OcrWorker.instance()
        worker.task_done.connect(self._on_anchor_ocr_done)
        worker.task_error.connect(self._on_anchor_ocr_error)
        self._anchor_ocr_connected = True

    def _recognize_anchor_item(self, cx: int, cy: int, anchor_type: str) -> None:
        self._connect_anchor_ocr_worker()
        WindowHelper.focus()
        self._mouse.move_and_click(cx, cy)

        def _capture_and_ocr() -> None:
            result = self._capture.capture(window=WindowHelper.find_genshin_window())
            if result is None:
                log.warning(f"[调试面板] 锚点识别({anchor_type}): 截图失败")
                return
            roi_configs = {
                name: (dx, dy, dw, dh)
                for name, dx, dy, dw, dh in ANCHOR_ROI_DEFINITIONS
            }
            task = self._create_anchor_ocr_task(result.image, roi_configs, anchor_type)
            from backend.automation.ocr_worker import OcrWorker

            OcrWorker.instance().submit(task, callback_data=anchor_type)

        QTimer.singleShot(200, _capture_and_ocr)

    @staticmethod
    def _create_anchor_ocr_task(image, roi_configs, anchor_type):
        def task(ocr) -> dict:
            from backend.automation.recognizer import ArtifactRecognizer
            from backend.ui.presenters.debug_panel.artifact_recognition_presenter import (
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

    def _on_anchor_ocr_done(self, result: dict, callback_data: object) -> None:
        if not isinstance(result, dict) or "anchor_type" not in result:
            return
        anchor_type = result["anchor_type"]
        display_text = "\n".join(result.get("display_lines", []))
        if anchor_type == "first":
            self._anchor_first_display_text = display_text
            self._anchor_first_recognized = True
            self.anchorFirstRecognizedChanged.emit()
            log.info(f"[调试面板] 首锚点识别完成:\n{display_text}")
        elif anchor_type == "tail":
            self._anchor_tail_display_text = display_text
            self._anchor_tail_recognized = True
            self.anchorTailRecognizedChanged.emit()
            log.info(f"[调试面板] 尾锚点识别完成:\n{display_text}")

    def _on_anchor_ocr_error(self, error: str, callback_data: object) -> None:
        log.error(f"[调试面板] 锚点OCR识别失败({callback_data}): {error}")

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
        def _task() -> object:
            slider_y = self._slider_scroller.ensure_at_top()
            if slider_y is None:
                return None
            final_y = self._slider_scroller.scroll_to_bottom(slider_y)
            return {"final_y": final_y, "slider_y": slider_y}

        def _on_done(result: object) -> None:
            if result is None:
                log.warning("[调试面板] 滚动到底: 未找到滑块")
                return
            self._anchor_scroll_running = True
            self.anchorScrollRunningChanged.emit()
            r = result
            if r["final_y"] is not None:
                self._on_smart_scroll_final_slider_y(r["final_y"])
            self._anchor_scroll_running = False
            self.anchorScrollRunningChanged.emit()

        self._run_in_background(_task).done.connect(_on_done)

    def _on_smart_scroll_final_slider_y(self, slider_y: int) -> None:
        def _task() -> object:
            window = WindowHelper.find_genshin_window()
            result = self._capture.capture(window=window)
            if result is None:
                raise GameWindowNotFoundError()
            det_result = SlotDetector.detect(result.image, config=self._active_config)
            if not det_result.slots:
                return None
            last_slot = det_result.slots[-1]
            return {"cx": last_slot.cx, "cy": last_slot.cy}

        def _on_done(result: object) -> None:
            if result is None:
                log.warning("[调试面板] 尾锚点定位: 未检测到格子")
                return
            r = result
            tail_cx, tail_cy = r["cx"], r["cy"]
            log.info(f"[调试面板] 尾锚点定位: 最后格子 ({tail_cx}, {tail_cy})")
            self._anchor_tail_x, self._anchor_tail_y = tail_cx, tail_cy
            self._anchor_last_x = tail_cx
            self._anchor_last_y = tail_cy
            self.anchorLastFound.emit()
            self._calculate_anchor_pages()

        self._run_in_background(_task).done.connect(_on_done)

    # ==================================================================
    # 颜色检测到底
    # ==================================================================

    @Slot()
    def checkScrollBottomByColor(self) -> None:
        def _task() -> object:
            slider_y, is_at_bottom = self._slider_scroller.check_bottom_by_color()
            if slider_y is None:
                return None
            if is_at_bottom:
                sr = self._active_config.slider_region()
                if sr is None:
                    raise ValueError("滑块区域未配置")
                region_x, _top_y, region_y, region_w, region_h = sr
                self._mouse.move_to(region_x + region_w // 2, region_y + region_h // 2)
                for _ in range(SliderDetector.EXTRA_TICKS):
                    self._mouse.scroll_one_tick()
                    sleep(0.03)
            return {"is_at_bottom": is_at_bottom}

        def _on_done(result: object) -> None:
            if result is None:
                log.warning("[调试面板] 颜色检测: 未找到滑块")
                return
            if result["is_at_bottom"]:
                log.info("[调试面板] 颜色检测: 已确认到底")

        self._run_in_background(_task).done.connect(_on_done)

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
        def _task() -> object:
            window = WindowHelper.find_genshin_window()
            result = self._capture.capture(window=window)
            if result is None:
                raise GameWindowNotFoundError()
            debug_rgb = DebugPreview.generate_grayscale(result.image)
            vkey = PreviewImageProvider.put("grayscale_snapshot", debug_rgb)
            return {
                "vkey": vkey,
                "w": result.image.shape[1],
                "h": result.image.shape[0],
            }

        def _on_done(result: object) -> None:
            self.debugPreviewReady.emit(result["vkey"])
            log.info(f"[调试面板] 灰度截图: {result['w']}x{result['h']}")

        self._run_in_background(_task).done.connect(_on_done)

    @Slot()
    def detectSlots(self) -> None:
        def _task() -> object:
            window = WindowHelper.find_genshin_window()
            result = self._capture.capture(window=window)
            if result is None:
                raise GameWindowNotFoundError()
            cfg = self._active_config
            det_result = SlotDetector.detect(result.image, config=cfg)
            debug_rgb = SlotDetector.draw_debug(
                result.image,
                det_result.slots,
                config=cfg,
                page_bottom=det_result.bottom_y,
                debug_infos=det_result.debug_infos,
            )
            vkey = PreviewImageProvider.put("slot_debug", debug_rgb)
            return {"vkey": vkey, "count": len(det_result.slots), "name": cfg.name}

        def _on_done(result: object) -> None:
            self.debugPreviewReady.emit(result["vkey"])
            log.info(
                f"[调试面板] 格子检测: 找到 {result['count']} 个格子 [{result['name']}]"
            )

        self._run_in_background(_task).done.connect(_on_done)

    @Slot(int)
    def detectSlotsRepeatedly(self, repeat_count: int) -> None:
        def _task() -> object:
            t0 = time.perf_counter()
            all_results: list[DetectResult] = []
            for i in range(repeat_count):
                window = WindowHelper.find_genshin_window()
                result = self._capture.capture(window=window)
                if result is None:
                    raise GameWindowNotFoundError()
                det_result = SlotDetector.detect(
                    result.image, config=self._active_config
                )
                all_results.append(det_result)
                log.info(
                    f"[调试面板] 连续检测 [{i + 1}/{repeat_count}]: {len(det_result.slots)} 个格子"
                )

            # 逐格比较：同一时间游戏画面不变，每次检测结果应完全一致
            base = all_results[0]
            diffs: list[str] = []
            for i in range(1, len(all_results)):
                cur = all_results[i]
                if len(cur.slots) != len(base.slots):
                    diffs.append(
                        f"第{i + 1}次数量不同: {len(base.slots)} → {len(cur.slots)}"
                    )
                    continue
                for s_base, s_cur in zip(base.slots, cur.slots):
                    sig = (s_base.row, s_base.col)
                    for attr in ("cx", "cy", "rarity", "star_count", "locked"):
                        v_base = getattr(s_base, attr)
                        v_cur = getattr(s_cur, attr)
                        if v_base != v_cur:
                            diffs.append(
                                f"第{i + 1}次 [{sig[0]},{sig[1]}] "
                                f"{attr}: {v_base} → {v_cur}"
                            )

            elapsed = (time.perf_counter() - t0) * 1000
            return {"diffs": diffs, "repeat_count": repeat_count,
                    "slot_count": len(base.slots), "elapsed_ms": elapsed}

        def _on_done(result: object) -> None:
            diffs = result["diffs"]
            repeat_count = result["repeat_count"]
            slot_count = result["slot_count"]
            elapsed_ms = result["elapsed_ms"]
            if not diffs:
                log.info(
                    f"[调试面板] 连续检测: 稳定 ✓ — "
                    f"{repeat_count}次均为{slot_count}个格子，"
                    f"所有属性完全一致 ({elapsed_ms:.0f}ms)"
                )
            else:
                log.warning(
                    f"[调试面板] 连续检测: 不稳定 ✗ — "
                    f"{len(diffs)}处差异 ({elapsed_ms:.0f}ms):\n"
                    + "\n".join(f"  • {d}" for d in diffs)
                )

        self._run_in_background(_task).done.connect(_on_done)


class _SlotClickWorker(QThread):
    """后台线程：基于 SlotIterator 逐格点击（调试面板批量点击用）"""

    progress = Signal(int, int)
    finished = Signal()

    def __init__(
        self,
        mouse: MouseController,
        det_result,
        click_interval_ms: int,
    ):
        super().__init__()
        self._mouse = mouse
        self._det_result = det_result
        self._click_interval_ms = click_interval_ms
        self._stop = False

    def stop(self) -> None:
        self._stop = True

    def run(self) -> None:
        iterator = SlotIterator(self._mouse)
        total = len(self._det_result.slots)

        def on_slot(slot, idx, _total):
            self.progress.emit(idx, total)
            return not self._stop

        iterator.iter_slots(
            self._det_result,
            on_slot=on_slot,
            stop_check=lambda: self._stop,
            click_delay=self._click_interval_ms / 1000.0,
        )
        self.finished.emit()