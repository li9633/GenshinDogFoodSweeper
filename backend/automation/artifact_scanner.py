"""
圣遗物扫描器 — 包含所有扫描工作线程和高层协调器
=============================================
从 ArtifactScanPresenter 中提取的 QThread Worker 类，
以及 ArtifactScanner 高层协调器。

所有 Worker 类可在任意上下文中使用（调试面板、正式功能页面等）。
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from time import perf_counter, sleep

from models.artifact import ArtifactInfo
from PySide6.QtCore import QThread, Signal
from utils.logger import log

from backend.automation.anchor_locator import AnchorLocator
from backend.automation.grid_calculator import GridCalculator
from backend.automation.grid_click_config import GridClickConfig
from backend.automation.mouse_controller import MouseController
from backend.automation.page_scroller import PageScroller
from backend.automation.recognizer import ArtifactRecognizer
from backend.automation.slider_detector import SliderDetector
from backend.automation.slider_scroller import SliderScroller
from backend.automation.slot_detector import (
    ArtifactRarity,
    SlotDetector,
    SlotDetectorConfig,
)
from backend.automation.window_helper import WindowHelper
from backend.models.artifact_recognition_field import ArtifactRecognitionField
from backend.utils.screen_capture import ScreenshotCapture
from backend.utils.settings_manager import settings

# 扫描识别策略：全部识别，仅跳过套装效果查询（省 DB 开销）
_SCAN_FIELDS: frozenset[ArtifactRecognitionField] = frozenset(
    {
        ArtifactRecognitionField.SET_NAME,
        ArtifactRecognitionField.PIECE_TYPE,
        ArtifactRecognitionField.MAIN_STAT,
        ArtifactRecognitionField.SUB_STATS,
        ArtifactRecognitionField.LEVEL,
        ArtifactRecognitionField.RARITY,
        ArtifactRecognitionField.LOCK_STATUS,
    }
)

# ====================================================================
# 网格点击核心函数
# ====================================================================


def run_grid_click(
    mouse: MouseController,
    config: GridClickConfig,
    on_click: Callable[[int, int, int, int, int, int], bool] | None = None,
    on_progress: Callable[[int, int], None] | None = None,
    stop_check: Callable[[], bool] | None = None,
    pre_check: Callable[[int, int], bool] | None = None,
    win: WindowHelper | None = None,
) -> None:
    """同步网格点击 — QThread 无关的纯逻辑函数。

    Args:
        mouse: 鼠标控制器
        config: 网格配置
        on_click: 每次点击后回调 (row, col, x, y, idx, total) -> bool
        on_progress: 进度回调 (idx, total)
        stop_check: 停止检查回调 () -> bool，返回 True 则停止
        pre_check: 点击前检查 (row, col) -> bool，返回 False 则跳过该格子
        win: 窗口助手，config.auto_focus=True 时用于聚焦窗口
    """
    if config.auto_focus and win:
        win.focus()

    total = config.rows * config.cols

    for idx, (row, col, x, y) in enumerate(
        GridCalculator.iter_cells(
            config.rows,
            config.cols,
            config.margin_x,
            config.margin_y,
            config.item_w,
            config.item_h,
            config.gap,
            config.origin_x,
            config.origin_y,
        ),
        start=1,
    ):
        if stop_check and stop_check():
            break
        if pre_check and not pre_check(row, col):
            continue
        mouse.move_and_click(x, y)
        if on_progress:
            on_progress(idx, total)
        if on_click and not on_click(row, col, x, y, idx, total):
            break
        sleep(config.interval_ms / 1000.0)


from backend.automation.artifact_count_ocr import ocr_artifact_count

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
        slot_config: SlotDetectorConfig,
        initial_slider_y: int,
        window_bottom: int,
    ):
        super().__init__()
        self._mouse = mouse
        self._capture = capture
        self._ox = ox
        self._oy = oy
        self._slot_config = slot_config
        self._initial_slider_y = initial_slider_y
        self._window_bottom = window_bottom
        self._stop = False
        self._win = WindowHelper(self._capture, self._mouse)
        self._page_scroller = PageScroller(self._mouse, self._capture)
        self._slider_scroller = SliderScroller(
            self._mouse,
            self._capture,
            self._win,
            self._slot_config,
        )

    def stop(self) -> None:
        self._stop = True

    def run(self) -> None:
        sr = self._slot_config.slider_region()
        if sr is None:
            return
        slider_x, _slider_top, slider_bottom, slider_w, slider_h = sr

        window_bottom = self._window_bottom
        drag_x = self._ox + slider_x + slider_w // 2
        mouse_total = (slider_bottom - self._initial_slider_y) * 4
        chunks = 3
        chunk = mouse_total // chunks
        prev_y = self._initial_slider_y

        for i in range(chunks):
            if self._stop:
                return
            drag_from_y = self._oy + prev_y + slider_h // 2
            drag_to_y = min(drag_from_y + chunk, window_bottom - 10)
            self._mouse.drag(
                drag_x,
                drag_from_y,
                drag_x,
                drag_to_y,
                SliderDetector.DRAG_STEPS,
                SliderDetector.DRAG_DELAY,
            )
            sleep(0.2)

            result = self._capture.capture()
            if result is None:
                continue
            current_y, _, _, _ = SliderDetector.find_slider(
                result.image,
                slider_x,
                max(0, slider_bottom - SliderDetector.MAX_SEARCH),
                slider_bottom,
                slider_w,
                slider_h,
            )
            if current_y is None:
                continue
            self.progress.emit(i + 1, chunks)
            if slider_bottom - current_y <= 5:
                prev_y = current_y
                break
            if abs(current_y - prev_y) <= 5:
                prev_y = current_y
                break
            prev_y = current_y

        confirmed = self._slider_scroller.verify_bottom(prev_y)
        if confirmed is not None:
            prev_y = confirmed

        abs_x = self._ox + slider_x + slider_w // 2
        abs_y = self._oy + slider_bottom + slider_h // 2
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
        anchor_first_x: int,
        anchor_first_y: int,
        anchor_first_w: int,
        anchor_first_h: int,
        slot_config: SlotDetectorConfig,
        scroll_flag_x: int,
        scroll_flag_y: int,
        tick_delay_ms: int,
        page_settle_ms: int,
        click_interval_ms: int,
        stop_mode: str = "anchor",
        on_complete: Callable[[list[ArtifactInfo]], None] | None = None,
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
        self._anchor_first_x = anchor_first_x
        self._anchor_first_y = anchor_first_y
        self._anchor_first_w = anchor_first_w
        self._anchor_first_h = anchor_first_h
        self._slot_config = slot_config
        self._scroll_flag_x = scroll_flag_x
        self._scroll_flag_y = scroll_flag_y
        self._tick_delay_ms = tick_delay_ms
        self._page_settle_ms = page_settle_ms
        self._click_interval_ms = click_interval_ms
        self._stop_mode = stop_mode
        self._on_complete = on_complete
        self._stop = False
        self._results: list[ArtifactInfo] = []
        self._tail_info: ArtifactInfo | None = None
        self._tail_is_material: bool = False
        self._win = WindowHelper(self._capture, self._mouse)
        self._slider_scroller = SliderScroller(
            self._mouse,
            self._capture,
            self._win,
            self._slot_config,
        )
        self._page_scroller: PageScroller = PageScroller(self._mouse, self._capture)

    def stop(self) -> None:
        self._stop = True

    def results(self) -> list[ArtifactInfo]:
        return self._results

    # ========== 主流程 ==========

    def run(self) -> None:
        try:
            # Step 0: 聚焦游戏窗口
            self.stepChanged.emit("正在聚焦游戏窗口...")
            self._win.focus()

            self.stepChanged.emit("正在初始化 OCR 引擎...")
            from backend.automation.ocr_engine import OcrEngine
            from backend.exceptions.automation import OcrModelNotReadyError

            ocr = OcrEngine.create_ocr(self._engines_dir)

            # Step 1-2: 识别数量 + 计算分页
            artifacts_per_page = self._slot_config.rows * self._slot_config.cols
            count = 0
            if self._slot_config.has_artifact_count:
                self.stepChanged.emit("正在识别背包圣遗物数量...")
                count = self._ocr_count(ocr)
                if self._stop:
                    return
                if count <= 0:
                    self.errorOccurred.emit(
                        "未能识别圣遗物数量，请确认已打开背包界面并切换到圣遗物页面"
                    )
                    return
            total_pages = (
                max(1, (count + artifacts_per_page - 1) // artifacts_per_page)
                if count > 0
                else 1
            )
            if count > 0:
                self.stepChanged.emit(f"共 {count} 个圣遗物, {total_pages} 页")
                effective_count = count
                if self._stop_mode == "fixed_count":
                    fixed_count = settings.get_int("scan.fixed_count")
                    if fixed_count > 0 and fixed_count < count:
                        effective_count = fixed_count
                        self.stepChanged.emit(
                            f"固定数量模式: 扫描 {effective_count} / {count} 件"
                        )
                self.progressChanged.emit(0, effective_count)
            else:
                self.stepChanged.emit(f"扫描模式: {self._slot_config.name}")

            # Step 3: 滑块到顶部
            self.stepChanged.emit("正在滚动到顶部...")
            self._scroll_to_top()
            if self._stop:
                return

            if self._stop_mode == "anchor":
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
                    first_info.page = 0
                    first_info.row = 0
                    first_info.col = 0
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
                det_result = SlotDetector.detect(result.image, config=self._slot_config)
                if self._stop:
                    return
                if det_result.slots:
                    last_slot = det_result.slots[-1]
                    tail_cx, tail_cy = last_slot.cx, last_slot.cy
                    self.stepChanged.emit("正在识别尾锚点...")
                    tail_info = self._click_and_recognize_artifact(
                        tail_cx, tail_cy, ocr
                    )
                    if self._stop:
                        return
                    if tail_info:
                        tail_info.page = -1
                        tail_info.row = -1
                        tail_info.col = -1
                        display = AnchorLocator.format_artifact_short(tail_info)
                        self.stepChanged.emit(f"尾锚点: {display}")
                        log.info(f"尾锚点识别: {display}")
                        if tail_info.is_material:
                            self._tail_info = tail_info
                            self._tail_is_material = True
                        else:
                            log.warning(
                                "尾锚点不是强化材料，无法使用锚点停止，将扫描至末尾"
                            )
                            self._tail_info = None
                            self._tail_is_material = False

                # Step 6: 回到滑块顶部
                self.stepChanged.emit("正在回到顶部...")
                self._scroll_to_top()
                if self._stop:
                    return

            # Step 7-8: 逐页扫描
            self._results = []
            scan_start_time = perf_counter()
            ox, oy = self._win.get_origin()

            effective_count = count
            if self._stop_mode == "fixed_count":
                fixed_count = settings.get_int("scan.fixed_count")
                if fixed_count > 0 and count > 0:
                    effective_count = min(fixed_count, count)
                elif fixed_count > 0:
                    effective_count = fixed_count

            grid_config = GridClickConfig(
                origin_x=ox,
                origin_y=oy,
                margin_x=self._margin_x,
                margin_y=self._margin_y,
                item_w=self._item_w,
                item_h=self._item_h,
                gap=self._gap,
                rows=self._slot_config.rows,
                cols=self._slot_config.cols,
                interval_ms=self._click_interval_ms,
            )

            def _scan_callback(
                row: int,
                col: int,
                x: int,
                y: int,
                idx: int,
                total: int,
            ) -> bool:
                if self._stop:
                    return False
                cx, cy = GridCalculator.cell_center(
                    self._margin_x,
                    self._margin_y,
                    self._item_w,
                    self._item_h,
                    self._gap,
                    row,
                    col,
                )
                screenshot = self._capture.capture()
                if screenshot and AnchorLocator.is_empty_slot(cx, cy, screenshot.image):
                    return True
                info = self._recognize_current_artifact(ocr)
                if info:
                    info.page = page
                    info.row = row
                    info.col = col

                    # 停止模式: 仅扫描五星 → 跳过非五星
                    stop_mode = settings.get("scan.stop_mode")
                    if (
                        stop_mode == "five_star_only"
                        and info.rarity != ArtifactRarity.FIVE
                    ):
                        return True

                    from backend.utils.artifact_deduplicator import (
                        ArtifactDeduplicator,
                    )

                    # 去重检查（仅对5星生效，由设置 scan.enable_dedup 控制）
                    if info.rarity == ArtifactRarity.FIVE and settings.get_bool(
                        "scan.enable_dedup"
                    ):
                        dup_existing = next(
                            (
                                e
                                for e in self._results
                                if ArtifactDeduplicator.is_duplicate(info, e)
                            ),
                            None,
                        )
                        if dup_existing is not None:
                            # 同位重复 → 面板未刷新，重新识别一次
                            if (
                                dup_existing.page == info.page
                                and dup_existing.row == info.row
                                and dup_existing.col == info.col
                            ):
                                log.debug(
                                    f"同位重复 P{page}R{row}C{col}，"
                                    f"面板未刷新，重新识别..."
                                )
                                info = self._recognize_current_artifact(ocr)
                                if info is None:
                                    return True
                                info.page = page
                                info.row = row
                                info.col = col
                                if any(
                                    ArtifactDeduplicator.is_duplicate(info, e)
                                    for e in self._results
                                ):
                                    return True
                            else:
                                return True

                    # 尾锚点检查：扫描到尾部标记（强化材料）→ 停止
                    if (
                        self._tail_info
                        and self._tail_is_material
                        and ArtifactDeduplicator.is_duplicate(info, self._tail_info)
                    ):
                        log.info("扫描到尾锚点(强化材料)，停止扫描")
                        self._stop = True
                        return False

                    self._results.append(info)
                    display = AnchorLocator.format_artifact_short(info)
                    self.artifactScanned.emit(display, info.is_material)
                    self.progressChanged.emit(
                        len(self._results),
                        min(fixed_count, count)
                        if (
                            stop_mode == "fixed_count"
                            and (fixed_count := settings.get_int("scan.fixed_count"))
                            > 0
                            and count > 0
                        )
                        else count,
                    )

                    # 停止模式: 固定数量
                    if stop_mode == "fixed_count":
                        fixed_count = settings.get_int("scan.fixed_count")
                        if fixed_count > 0 and len(self._results) >= fixed_count:
                            log.info(
                                f"已扫描{len(self._results)}件，"
                                f"达到固定数量{fixed_count}，停止扫描"
                            )
                            self._stop = True
                            return False

                    # 进度 ETA 日志
                    elapsed = perf_counter() - scan_start_time
                    if stop_mode == "fixed_count":
                        fixed_count = settings.get_int("scan.fixed_count")
                        effective_count = (
                            min(fixed_count, count)
                            if fixed_count > 0 and count > 0
                            else (count if count > 0 else fixed_count)
                        )
                    else:
                        effective_count = count
                    if effective_count > 0 and len(self._results) > 0:
                        avg = elapsed / len(self._results)
                        remaining = avg * (effective_count - len(self._results))
                        log.info(
                            f"当前已扫描{len(self._results)}个圣遗物，"
                            f"共{effective_count}个，"
                            f"已用时{int(elapsed // 60):02d}:{int(elapsed % 60):02d}，"
                            f"预计剩余{int(remaining // 60):02d}:{int(remaining % 60):02d}"
                        )

                    # OCR 数量检查（次要停止条件，兜底安全；仅当有数量时生效）
                    if count > 0 and len(self._results) >= count:
                        log.info(
                            f"已扫描{len(self._results)}件，达到OCR数量{count}，"
                            f"停止扫描"
                        )
                        self._stop = True
                        return False
                return True

            for page in range(total_pages):
                if self._stop:
                    break
                self.stepChanged.emit(f"正在扫描第 {page + 1}/{total_pages} 页...")
                self.pageChanged.emit(page + 1, total_pages)

                # 仅五星模式：每页扫描前检测格子星级，跳过非五星格子
                stop_mode = settings.get("scan.stop_mode")
                if stop_mode == "five_star_only":
                    screenshot = self._capture.capture()
                    if screenshot:
                        det = SlotDetector.detect(
                            screenshot.image, config=self._slot_config
                        )
                        slot_rarity = {(s.row, s.col): s.rarity for s in det.slots}
                        pre_check = lambda r, c, _m=slot_rarity: (
                            _m.get((r, c)) == ArtifactRarity.FIVE
                        )
                    else:
                        pre_check = None
                else:
                    pre_check = None

                run_grid_click(
                    self._mouse,
                    grid_config,
                    on_click=_scan_callback,
                    stop_check=lambda: self._stop,
                    pre_check=pre_check,
                )

                if page < total_pages - 1 and not self._stop:
                    self._scroll_one_page()

            # Step 9: 数量对比验证
            scanned = len(self._results)
            if count > 0:
                if self._stop_mode == "fixed_count":
                    log.info(f"固定数量扫描完成: {scanned}件")
                elif scanned < count:
                    log.warning(
                        f"数量不匹配: 背包{count}个, 实际识别{scanned}个, "
                        f"差异{count - scanned}个"
                    )
            if count > 0:
                self.stepChanged.emit(f"扫描完成: 背包{count}个, 识别{scanned}个")
            else:
                self.stepChanged.emit(f"扫描完成: 识别{scanned}个")

            # 触发完成回调（可扩展：自行实现入库、导出等逻辑）
            if self._on_complete:
                self._on_complete(self._results)

            self.finished.emit(scanned, count)

        except OcrModelNotReadyError:
            # 异常已在 __init__ 中完成 log.error + GMessageBox 弹窗
            self.finished.emit(0, 0)
        except Exception as exc:
            import traceback

            self.errorOccurred.emit(f"{exc}\n{traceback.format_exc()}")

    # ========== 窗口工具 ==========

    def _focus_game(self) -> None:
        self._win.focus()

    # ========== OCR 数量识别 ==========

    def _ocr_count(self, ocr) -> int:
        return ocr_artifact_count(self._capture, ocr)

    # ========== 滑块操作 ==========

    def _scroll_to_top(self) -> None:
        self._slider_scroller.ensure_at_top()

    def _scroll_to_bottom(self) -> int | None:
        sr = self._slot_config.slider_region()
        if sr is None:
            return None
        slider_x, slider_top, slider_bottom, slider_w, slider_h = sr

        self._win.focus()
        ox, oy = self._win.get_origin()
        result = self._capture.capture()
        if result is None:
            return None
        slider_y, _, _, _ = SliderDetector.find_slider(
            result.image,
            slider_x,
            slider_top,
            slider_bottom,
            slider_w,
            slider_h,
        )
        if slider_y is None:
            log.warning("滚动到底: 未检测到滑块")
            return None
        if slider_y - slider_top > SliderDetector.PROXIMITY:
            log.info("滚动到底: 先回到顶部...")
            self._scroll_to_top()
            result = self._capture.capture()
            if result is None:
                return None
            slider_y, _, _, _ = SliderDetector.find_slider(
                result.image,
                slider_x,
                slider_top,
                slider_bottom,
                slider_w,
                slider_h,
            )
            if slider_y is None:
                return None

        slider_total = slider_bottom - slider_y
        if slider_total <= 0:
            log.info("滚动到底: 滑块已在底部")
            return slider_y

        window = self._capture.find_genshin_window()
        window_bottom = (oy + window.height) if window else (oy + 1000)
        drag_x = ox + slider_x + slider_w // 2
        mouse_total = slider_total * 4
        chunks = 3
        chunk = mouse_total // chunks
        prev_y = slider_y

        for _ in range(chunks):
            if self._stop:
                return None
            drag_from_y = oy + prev_y + slider_h // 2
            drag_to_y = min(drag_from_y + chunk, window_bottom - 10)
            self._mouse.drag(
                drag_x,
                drag_from_y,
                drag_x,
                drag_to_y,
                SliderDetector.DRAG_STEPS,
                SliderDetector.DRAG_DELAY,
            )
            sleep(0.2)
            result = self._capture.capture()
            if result is None:
                continue
            current_y, _, _, _ = SliderDetector.find_slider(
                result.image,
                slider_x,
                max(0, slider_bottom - SliderDetector.MAX_SEARCH),
                slider_bottom,
                slider_w,
                slider_h,
            )
            if current_y is None:
                continue
            if slider_bottom - current_y <= 5:
                prev_y = current_y
                break
            if abs(current_y - prev_y) <= 5:
                prev_y = current_y
                break
            prev_y = current_y

        confirmed = self._slider_scroller.verify_bottom(prev_y)
        if confirmed is not None:
            prev_y = confirmed

        abs_x = ox + slider_x + slider_w // 2
        abs_y = oy + slider_bottom + slider_h // 2
        self._mouse.move_to(abs_x, abs_y)
        for _ in range(SliderDetector.EXTRA_TICKS):
            if self._stop:
                return None
            self._mouse.scroll_one_tick()
            sleep(0.03)
        log.info(f"滚动到底: 完成, slider_y={prev_y}")
        return prev_y

    # ========== 圣遗物识别 ==========

    def _click_and_recognize_artifact(
        self, cx: int, cy: int, ocr
    ) -> ArtifactInfo | None:
        ox, oy = self._win.get_origin()
        self._mouse.move_and_click(ox + cx, oy + cy)
        return self._recognize_current_artifact(ocr)

    def _recognize_current_artifact(self, ocr) -> ArtifactInfo | None:
        sleep(0.15)  # 等待游戏详情面板刷新
        result = self._capture.capture()
        if result is None:
            return None
        try:
            return ArtifactRecognizer.recognize(
                result.image,
                self._slot_config.detail_roi_configs,
                ocr,
                fields=_SCAN_FIELDS,
                lock_anchor_search_region=self._slot_config.lock_anchor_search_region,
                lock_anchor_to_level=self._slot_config.lock_anchor_to_level,
                lock_anchor_to_sub_stats=self._slot_config.lock_anchor_to_sub_stats,
            )
        except Exception as exc:
            log.error(f"圣遗物识别失败: {exc}")
            return None

    # ========== 翻页 ==========

    def _scroll_one_page(self) -> None:
        ox, oy = self._win.get_origin()
        self._page_scroller.scroll_to_next_page(
            ox,
            oy,
            self._scroll_flag_x,
            self._scroll_flag_y,
            self._tick_delay_ms,
            self._page_settle_ms,
        )
