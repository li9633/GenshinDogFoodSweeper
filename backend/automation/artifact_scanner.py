"""
圣遗物扫描器 — 包含所有扫描工作线程和高层协调器
=============================================
从 ArtifactScanPresenter 中提取的 QThread Worker 类，
以及 ArtifactScanner 高层协调器。

所有 Worker 类可在任意上下文中使用（调试面板、正式功能页面等）。
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from time import sleep

from models.artifact import ArtifactInfo
from PySide6.QtCore import QThread, Signal
from utils.logger import log

from backend.automation.anchor_locator import AnchorLocator
from backend.automation.grid_calculator import GridCalculator
from backend.automation.grid_click_config import GridClickConfig
from backend.automation.mouse_controller import MouseController
from backend.automation.recognizer import ArtifactRecognizer
from backend.automation.slider_detector import SliderDetector
from backend.automation.slider_scroller import SliderScroller
from backend.automation.window_helper import WindowHelper
from backend.utils.screen_capture import ScreenshotCapture

# ====================================================================
# 网格点击核心函数
# ====================================================================


def run_grid_click(
    mouse: MouseController,
    config: GridClickConfig,
    on_click: Callable[[int, int, int, int, int, int], bool] | None = None,
    on_progress: Callable[[int, int], None] | None = None,
    stop_check: Callable[[], bool] | None = None,
    win: WindowHelper | None = None,
) -> None:
    """同步网格点击 — QThread 无关的纯逻辑函数。

    Args:
        mouse: 鼠标控制器
        config: 网格配置
        on_click: 每次点击后回调 (row, col, x, y, idx, total) -> bool
        on_progress: 进度回调 (idx, total)
        stop_check: 停止检查回调 () -> bool，返回 True 则停止
        win: 窗口助手，config.auto_focus=True 时用于聚焦窗口
    """
    if config.auto_focus and win:
        win.focus()

    total = config.rows * config.cols

    for idx, (row, col, x, y) in enumerate(
        GridCalculator.iter_cells(
            config.rows, config.cols,
            config.margin_x, config.margin_y,
            config.item_w, config.item_h, config.gap,
            config.origin_x, config.origin_y,
        ),
        start=1,
    ):
        if stop_check and stop_check():
            break
        mouse.move_and_click(x, y)
        if on_progress:
            on_progress(idx, total)
        if on_click and not on_click(row, col, x, y, idx, total):
            break
        sleep(config.interval_ms / 1000.0)


# ====================================================================
# 基础 Worker
# ====================================================================


class BatchClickWorker(QThread):
    """后台线程：逐行逐列点击网格

    支持可选的 on_click 回调：
        on_click(row, col, x, y, idx, total) -> bool
        返回 True 继续，False 停止。
        不传回调时仅点击，适用于调试面板。
    """

    progress = Signal(int, int)
    finished = Signal()

    def __init__(
        self,
        mouse: MouseController,
        config: GridClickConfig,
        on_click: Callable[[int, int, int, int, int, int], bool] | None = None,
        win: WindowHelper | None = None,
    ):
        super().__init__()
        self._mouse = mouse
        self._config = config
        self._on_click = on_click
        self._win = win
        self._stop = False

    def stop(self) -> None:
        self._stop = True

    def run(self) -> None:
        run_grid_click(
            self._mouse,
            self._config,
            on_click=self._on_click,
            on_progress=lambda idx, total: self.progress.emit(idx, total),
            stop_check=lambda: self._stop,
            win=self._win,
        )
        self.finished.emit()


class ScrollOneRowWorker(QThread):
    """后台线程：滚动指定格数"""

    progress = Signal(int)
    finished = Signal()

    def __init__(
        self,
        mouse: MouseController,
        flag_x: int,
        flag_y: int,
        delay_ms: int,
        origin_x: int,
        origin_y: int,
        ticks: int = 10,
    ):
        super().__init__()
        self._mouse = mouse
        self._flag_x = flag_x
        self._flag_y = flag_y
        self._delay_ms = delay_ms
        self._origin_x = origin_x
        self._origin_y = origin_y
        self._ticks = ticks

    def run(self) -> None:
        for i in range(1, self._ticks + 1):
            self._mouse.move_to(
                self._origin_x + self._flag_x,
                self._origin_y + self._flag_y,
            )
            self._mouse.scroll_one_tick()
            self.progress.emit(i)
            sleep(self._delay_ms / 1000.0)

        self.finished.emit()


class AutoScrollWorker(QThread):
    """后台线程：自动翻页，逐页滚动直到最后一页"""

    progress = Signal(int, int)
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
        ticks_per_page = self._ticks_per_row * self.ROWS_PER_PAGE

        for page in range(1, self._total_pages + 1):
            if self._stop:
                break
            self.progress.emit(page, self._total_pages)

            for _ in range(ticks_per_page):
                if self._stop:
                    break
                self._mouse.move_to(
                    self._origin_x + self._flag_x,
                    self._origin_y + self._flag_y,
                )
                self._mouse.scroll_one_tick()
                sleep(self._tick_delay_ms / 1000.0)

            sleep(self._page_settle_ms / 1000.0)

        self.finished.emit()


# ====================================================================
# 智能拖拽到底 Worker
# ====================================================================


class SmartScrollToBottomWorker(QThread):
    """后台线程：智能滚动到底部

    闯关逻辑：
    1. 逐段拖拽滑块向下
    2. 每次拖拽后截图检测滑块位置
    3. 滑块停止移动 → 碰到滑轨墙壁 → 确认到底
    4. 滑块消失且检测到滑轨颜色 → 确认到底
    """

    progress = Signal(int, int)
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
        self._win = WindowHelper(self._capture, self._mouse)
        self._slider_scroller = SliderScroller(
            self._mouse, self._capture, self._win,
        )

    def stop(self) -> None:
        self._stop = True

    def run(self) -> None:
        window_bottom = self._window_bottom
        drag_x = self._ox + self._region_x + self._region_w // 2
        mouse_total = (self._region_y - self._initial_slider_y) * 4
        chunks = 3
        chunk = mouse_total // chunks
        prev_y = self._initial_slider_y

        # 阶段1：逐段拖拽
        for i in range(chunks):
            if self._stop:
                return
            drag_from_y = self._oy + prev_y + self._region_h // 2
            drag_to_y = min(drag_from_y + chunk, window_bottom - 10)
            self._mouse.drag(
                drag_x, drag_from_y, drag_x, drag_to_y,
                SliderDetector.DRAG_STEPS, SliderDetector.DRAG_DELAY,
            )
            sleep(0.2)

            result = self._capture.capture()
            if result is None:
                continue
            current_y, _, _, _ = SliderDetector.find_slider(
                result.image,
                self._region_x,
                max(0, self._region_y - SliderDetector.MAX_SEARCH),
                self._region_y,
                self._region_w,
                self._region_h,
            )
            if current_y is None:
                continue
            self.progress.emit(i + 1, chunks)
            if self._region_y - current_y <= 5:
                prev_y = current_y
                break
            if abs(current_y - prev_y) <= 5:
                prev_y = current_y
                break
            prev_y = current_y

        # 阶段2：闯关验证 — 委托 SliderScroller
        confirmed = self._slider_scroller.verify_bottom(
            self._region_x, self._region_y,
            self._region_w, self._region_h, prev_y,
        )
        if confirmed is not None:
            prev_y = confirmed

        # 追加滚动确保到底
        abs_x = self._ox + self._region_x + self._region_w // 2
        abs_y = self._oy + self._region_y + self._region_h // 2
        self._mouse.move_to(abs_x, abs_y)
        for _ in range(SliderDetector.EXTRA_TICKS):
            if self._stop:
                return
            self._mouse.scroll_one_tick()
            sleep(0.03)

        self.final_slider_y.emit(prev_y)
        self.finished.emit()


# ====================================================================
# 全量扫描 Worker
# ====================================================================


class FullScanWorker(QThread):
    """后台线程：圣遗物全量扫描

    步骤：
    1. 识别背包圣遗物数量 → 2. 计算分页 → 3. 滑块到顶部
    4. 识别首锚点 → 5. 滑块到底 → 定位尾锚点 → 识别尾锚点
    6. 回到滑块顶部 → 7. 逐格点击+OCR识别
    8. 自动翻页重复 → 9. 数量对比验证
    """

    stepChanged = Signal(str)
    progressChanged = Signal(int, int)
    pageChanged = Signal(int, int)
    artifactScanned = Signal(str, bool)
    finished = Signal(int, int)
    errorOccurred = Signal(str)

    ARTIFACTS_PER_PAGE = 32
    ROWS = 4
    COLS = 8

    def __init__(
        self,
        mouse: MouseController,
        capture: ScreenshotCapture,
        engines_dir: Path,
        margin_x: int,
        margin_y: int,
        item_w: int,
        item_h: int,
        gap: int,
        roi_configs: dict,
        anchor_first_x: int,
        anchor_first_y: int,
        anchor_first_w: int,
        anchor_first_h: int,
        slider_region_x: int,
        slider_top_y: int,
        slider_bottom_y: int,
        slider_region_w: int,
        slider_region_h: int,
        scroll_flag_x: int,
        scroll_flag_y: int,
        ticks_per_row: int,
        tick_delay_ms: int,
        page_settle_ms: int,
        click_interval_ms: int,
    ):
        super().__init__()
        self._mouse = mouse
        self._capture = capture
        self._engines_dir = engines_dir
        self._margin_x = margin_x
        self._margin_y = margin_y
        self._item_w = item_w
        self._item_h = item_h
        self._gap = gap
        self._roi_configs = roi_configs
        self._anchor_first_x = anchor_first_x
        self._anchor_first_y = anchor_first_y
        self._anchor_first_w = anchor_first_w
        self._anchor_first_h = anchor_first_h
        self._slider_region_x = slider_region_x
        self._slider_top_y = slider_top_y
        self._slider_bottom_y = slider_bottom_y
        self._slider_region_w = slider_region_w
        self._slider_region_h = slider_region_h
        self._scroll_flag_x = scroll_flag_x
        self._scroll_flag_y = scroll_flag_y
        self._ticks_per_row = ticks_per_row
        self._tick_delay_ms = tick_delay_ms
        self._page_settle_ms = page_settle_ms
        self._click_interval_ms = click_interval_ms
        self._stop = False
        self._results: list[ArtifactInfo] = []
        self._win = WindowHelper(self._capture, self._mouse)
        self._slider_scroller = SliderScroller(
            self._mouse, self._capture, self._win,
        )

    def stop(self) -> None:
        self._stop = True

    def results(self) -> list[ArtifactInfo]:
        return self._results

    # ========== 主流程 ==========

    def run(self) -> None:
        try:
            self.stepChanged.emit("正在初始化 OCR 引擎...")
            from backend.automation.ocr_engine import OcrEngine

            ocr = OcrEngine._create_paddle_ocr(self._engines_dir)

            # Step 1-2: 识别数量 + 计算分页
            self.stepChanged.emit("正在识别背包圣遗物数量...")
            count = self._ocr_count(ocr)
            if self._stop:
                return
            if count <= 0:
                self.errorOccurred.emit("未能识别圣遗物数量，请确认背包界面已打开")
                return
            total_pages = max(
                1, (count + self.ARTIFACTS_PER_PAGE - 1) // self.ARTIFACTS_PER_PAGE
            )
            self.stepChanged.emit(f"共 {count} 个圣遗物, {total_pages} 页")
            self.progressChanged.emit(0, count)

            # Step 3: 滑块到顶部
            self.stepChanged.emit("正在滚动到顶部...")
            self._scroll_to_top()
            if self._stop:
                return

            # Step 4: 识别首锚点
            self.stepChanged.emit("正在识别首锚点...")
            first_info = self._click_and_recognize_artifact(
                self._anchor_first_x + self._anchor_first_w // 2,
                self._anchor_first_y + self._anchor_first_h // 2,
                ocr,
            )
            if self._stop:
                return
            if first_info:
                display = AnchorLocator.format_artifact_short(first_info)
                self.stepChanged.emit(f"首锚点: {display}")
                log.info(f"首锚点识别: {display}")

            # Step 5: 滑块到底 + 定位尾锚点 + 识别
            self.stepChanged.emit("正在滚动到底部...")
            slider_y = self._scroll_to_bottom()
            if self._stop:
                return
            if slider_y is None:
                self.errorOccurred.emit("滑块到底失败，无法定位尾锚点")
                return

            self.stepChanged.emit("正在定位尾锚点...")
            result = self._capture.capture()
            if result is None:
                self.errorOccurred.emit("截图失败")
                return
            tail_pos = AnchorLocator.find_tail_anchor(
                result.image, slider_y,
                self._anchor_first_x, self._anchor_first_y,
                self._anchor_first_w, self._anchor_first_h,
                self._gap,
            )
            if self._stop:
                return
            if tail_pos:
                tail_cx, tail_cy = tail_pos
                self.stepChanged.emit("正在识别尾锚点...")
                tail_info = self._click_and_recognize_artifact(tail_cx, tail_cy, ocr)
                if self._stop:
                    return
                if tail_info:
                    display = AnchorLocator.format_artifact_short(tail_info)
                    self.stepChanged.emit(f"尾锚点: {display}")
                    log.info(f"尾锚点识别: {display}")

            # Step 6: 回到滑块顶部
            self.stepChanged.emit("正在回到顶部...")
            self._scroll_to_top()
            if self._stop:
                return

            # Step 7-8: 逐页扫描
            self._results = []
            ox, oy = self._win.get_origin()

            grid_config = GridClickConfig(
                origin_x=ox, origin_y=oy,
                margin_x=self._margin_x, margin_y=self._margin_y,
                item_w=self._item_w, item_h=self._item_h, gap=self._gap,
                rows=self.ROWS, cols=self.COLS,
                interval_ms=self._click_interval_ms,
            )

            def _scan_callback(
                row: int, col: int, x: int, y: int,
                idx: int, total: int,
            ) -> bool:
                if self._stop:
                    return False
                cx, cy = GridCalculator.cell_center(
                    self._margin_x, self._margin_y,
                    self._item_w, self._item_h, self._gap,
                    row, col,
                )
                screenshot = self._capture.capture()
                if screenshot and AnchorLocator.is_empty_slot(
                    cx, cy, screenshot.image
                ):
                    return True
                info = self._recognize_current_artifact(ocr)
                if info:
                    self._results.append(info)
                    display = AnchorLocator.format_artifact_short(info)
                    self.artifactScanned.emit(display, info.is_material)
                    self.progressChanged.emit(len(self._results), count)
                return True

            for page in range(total_pages):
                if self._stop:
                    break
                self.stepChanged.emit(f"正在扫描第 {page + 1}/{total_pages} 页...")
                self.pageChanged.emit(page + 1, total_pages)

                run_grid_click(
                    self._mouse,
                    grid_config,
                    on_click=_scan_callback,
                    stop_check=lambda: self._stop,
                )

                if page < total_pages - 1 and not self._stop:
                    self._scroll_one_page()

            # Step 9: 数量对比验证
            scanned = len(self._results)
            if scanned < count:
                log.warning(
                    f"数量不匹配: 背包{count}个, 实际识别{scanned}个, "
                    f"差异{count - scanned}个"
                )
            self.stepChanged.emit(f"扫描完成: 背包{count}个, 识别{scanned}个")
            self.finished.emit(scanned, count)

        except Exception as exc:
            import traceback
            self.errorOccurred.emit(f"{exc}\n{traceback.format_exc()}")

    # ========== 窗口工具 ==========

    def _focus_game(self) -> None:
        self._win.focus()

    # ========== OCR 数量识别 ==========

    def _ocr_count(self, ocr) -> int:
        result = self._capture.capture()
        if result is None:
            return 0
        img = result.image
        h, w = img.shape[:2]
        roi_x, roi_y = 1606, 52
        roi_w, roi_h = 206, 49
        x1 = max(0, roi_x)
        y1 = max(0, roi_y)
        x2 = min(w, roi_x + roi_w)
        y2 = min(h, roi_y + roi_h)
        if x2 <= x1 or y2 <= y1:
            return 0
        cropped = img[y1:y2, x1:x2].copy()
        ocr_result = ocr.ocr(cropped)
        texts: list[str] = []
        if ocr_result and ocr_result[0]:
            r = ocr_result[0]
            if isinstance(r, dict):
                texts = [t for t in r.get("rec_texts", []) if t and t.strip()]
            elif hasattr(r, "rec_texts"):
                texts = [t for t in r.rec_texts if t and t.strip()]
        full_text = "".join(texts)
        m = re.search(r"(\d+)\s*/\s*\d+", full_text)
        if m:
            return int(m.group(1))
        m2 = re.search(r"\d+", full_text)
        return int(m2.group(0)) if m2 else 0

    # ========== 滑块操作 ==========

    def _scroll_to_top(self) -> None:
        self._slider_scroller.ensure_at_top(
            self._slider_region_x, self._slider_top_y,
            self._slider_bottom_y, self._slider_region_w, self._slider_region_h,
        )

    def _scroll_to_bottom(self) -> int | None:
        self._win.focus()
        ox, oy = self._win.get_origin()
        result = self._capture.capture()
        if result is None:
            return None
        slider_y, _, _, _ = SliderDetector.find_slider(
            result.image,
            self._slider_region_x, self._slider_top_y,
            self._slider_bottom_y, self._slider_region_w, self._slider_region_h,
        )
        if slider_y is None:
            log.warning("滚动到底: 未检测到滑块")
            return None
        if slider_y - self._slider_top_y > SliderDetector.PROXIMITY:
            log.info("滚动到底: 先回到顶部...")
            self._scroll_to_top()
            result = self._capture.capture()
            if result is None:
                return None
            slider_y, _, _, _ = SliderDetector.find_slider(
                result.image,
                self._slider_region_x, self._slider_top_y,
                self._slider_bottom_y, self._slider_region_w, self._slider_region_h,
            )
            if slider_y is None:
                return None

        slider_total = self._slider_bottom_y - slider_y
        if slider_total <= 0:
            log.info("滚动到底: 滑块已在底部")
            return slider_y

        window = self._capture.find_genshin_window()
        window_bottom = (oy + window.height) if window else (oy + 1000)
        drag_x = ox + self._slider_region_x + self._slider_region_w // 2
        mouse_total = slider_total * 4
        chunks = 3
        chunk = mouse_total // chunks
        prev_y = slider_y

        for _ in range(chunks):
            if self._stop:
                return None
            drag_from_y = oy + prev_y + self._slider_region_h // 2
            drag_to_y = min(drag_from_y + chunk, window_bottom - 10)
            self._mouse.drag(
                drag_x, drag_from_y, drag_x, drag_to_y,
                SliderDetector.DRAG_STEPS, SliderDetector.DRAG_DELAY,
            )
            sleep(0.2)
            result = self._capture.capture()
            if result is None:
                continue
            current_y, _, _, _ = SliderDetector.find_slider(
                result.image,
                self._slider_region_x,
                max(0, self._slider_bottom_y - SliderDetector.MAX_SEARCH),
                self._slider_bottom_y,
                self._slider_region_w, self._slider_region_h,
            )
            if current_y is None:
                continue
            if self._slider_bottom_y - current_y <= 5:
                prev_y = current_y
                break
            if abs(current_y - prev_y) <= 5:
                prev_y = current_y
                break
            prev_y = current_y

        confirmed = self._slider_scroller.verify_bottom(
            self._slider_region_x, self._slider_bottom_y,
            self._slider_region_w, self._slider_region_h, prev_y,
        )
        if confirmed is not None:
            prev_y = confirmed

        abs_x = ox + self._slider_region_x + self._slider_region_w // 2
        abs_y = oy + self._slider_bottom_y + self._slider_region_h // 2
        self._mouse.move_to(abs_x, abs_y)
        for _ in range(SliderDetector.EXTRA_TICKS):
            if self._stop:
                return None
            self._mouse.scroll_one_tick()
            sleep(0.03)
        log.info(f"滚动到底: 完成, slider_y={prev_y}")
        return prev_y

    # ========== 圣遗物识别 ==========

    def _click_and_recognize_artifact(self, cx: int, cy: int, ocr) -> ArtifactInfo | None:
        ox, oy = self._win.get_origin()
        self._mouse.move_and_click(ox + cx, oy + cy)
        sleep(0.2)
        return self._recognize_current_artifact(ocr)

    def _recognize_current_artifact(self, ocr) -> ArtifactInfo | None:
        result = self._capture.capture()
        if result is None:
            return None
        try:
            return ArtifactRecognizer.recognize(result.image, self._roi_configs, ocr)
        except Exception as exc:
            log.error(f"圣遗物识别失败: {exc}")
            return None

    # ========== 翻页 ==========

    def _scroll_one_page(self) -> None:
        ox, oy = self._win.get_origin()
        ticks_per_page = self._ticks_per_row * self.ROWS
        for _ in range(ticks_per_page):
            if self._stop:
                return
            self._mouse.move_to(ox + self._scroll_flag_x, oy + self._scroll_flag_y)
            self._mouse.scroll_one_tick()
            sleep(self._tick_delay_ms / 1000.0)
        sleep(self._page_settle_ms / 1000.0)