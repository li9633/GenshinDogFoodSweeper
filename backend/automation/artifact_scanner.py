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
from backend.automation.slot_iterator import SlotIterator
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

from backend.automation.artifact_count_ocr import ocr_artifact_count

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
        self._tick_delay_ms = tick_delay_ms
        self._page_settle_ms = page_settle_ms
        self._click_interval_ms = click_interval_ms
        self._stop_mode = stop_mode
        self._on_complete = on_complete
        self._stop = False
        self._results: list[ArtifactInfo] = []
        self._tail_info: ArtifactInfo | None = None
        self._tail_is_material: bool = False
        self._slider_scroller = SliderScroller(
            self._mouse,
            self._capture,
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
            # Step 0: 聚焦游戏窗口 + 注入坐标转换
            self.stepChanged.emit("正在聚焦游戏窗口...")
            WindowHelper.focus()
            MouseController.set_origin(WindowHelper.get_origin())

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
                window = WindowHelper.find_genshin_window()
                result = self._capture.capture(window=window)
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

            effective_count = count
            if self._stop_mode == "fixed_count":
                fixed_count = settings.get_int("scan.fixed_count")
                if fixed_count > 0 and count > 0:
                    effective_count = min(fixed_count, count)
                elif fixed_count > 0:
                    effective_count = fixed_count

            iterator = SlotIterator(self._mouse)

            for page in range(total_pages):
                if self._stop:
                    break
                self.stepChanged.emit(f"正在扫描第 {page + 1}/{total_pages} 页...")
                self.pageChanged.emit(page + 1, total_pages)

                window = WindowHelper.find_genshin_window()
                screenshot = self._capture.capture(window=window)
                if screenshot is None:
                    continue
                det_result = SlotDetector.detect(
                    screenshot.image, config=self._slot_config
                )
                if not det_result.slots:
                    break

                stop_mode = settings.get("scan.stop_mode")
                pre_check = (
                    (lambda s: s.rarity == ArtifactRarity.FIVE)
                    if stop_mode == "five_star_only"
                    else None
                )

                def on_slot(slot, idx, total, _page=page, _window=window):
                    if self._stop:
                        return False
                    shot = self._capture.capture(window=_window)
                    if shot and AnchorLocator.is_empty_slot(
                        slot.cx, slot.cy, shot.image
                    ):
                        return True
                    info = self._recognize_current_artifact(ocr)
                    if info:
                        info.page = _page
                        info.row = slot.row
                        info.col = slot.col

                        stop_mode = settings.get("scan.stop_mode")
                        if (
                            stop_mode == "five_star_only"
                            and info.rarity != ArtifactRarity.FIVE
                        ):
                            return True

                        from backend.utils.artifact_deduplicator import (
                            ArtifactDeduplicator,
                        )

                        if (
                            stop_mode == "five_star_only"
                            and info.rarity == ArtifactRarity.FIVE
                            and settings.get_bool("scan.enable_dedup")
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
                                if (
                                    dup_existing.page == info.page
                                    and dup_existing.row == info.row
                                    and dup_existing.col == info.col
                                ):
                                    log.debug(
                                        f"同位重复 P{_page}R{slot.row}C{slot.col}，"
                                        f"面板未刷新，重新识别..."
                                    )
                                    info = self._recognize_current_artifact(ocr)
                                    if info is None:
                                        return True
                                    info.page = _page
                                    info.row = slot.row
                                    info.col = slot.col
                                    if any(
                                        ArtifactDeduplicator.is_duplicate(info, e)
                                        for e in self._results
                                    ):
                                        return True
                                else:
                                    return True

                        if (
                            self._tail_info
                            and self._tail_is_material
                            and ArtifactDeduplicator.is_duplicate(
                                info, self._tail_info
                            )
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

                        if stop_mode == "fixed_count":
                            fixed_count = settings.get_int("scan.fixed_count")
                            if fixed_count > 0 and len(self._results) >= fixed_count:
                                log.info(
                                    f"已扫描{len(self._results)}件，"
                                    f"达到固定数量{fixed_count}，停止扫描"
                                )
                                self._stop = True
                                return False

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

                        if count > 0 and len(self._results) >= count:
                            log.info(
                                f"已扫描{len(self._results)}件，达到OCR数量{count}，"
                                f"停止扫描"
                            )
                            self._stop = True
                            return False
                    return True

                iterator.reset()
                iterator.iter_slots(
                    det_result,
                    on_slot=on_slot,
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
            self.errorOccurred.emit(OcrModelNotReadyError._MESSAGE)
        except Exception as exc:
            import traceback

            self.errorOccurred.emit(f"{exc}\n{traceback.format_exc()}")

    # ========== 窗口工具 ==========

    def _focus_game(self) -> None:
        WindowHelper.focus()

    # ========== OCR 数量识别 ==========

    def _ocr_count(self, ocr) -> int:
        return ocr_artifact_count(self._capture, ocr)

    # ========== 滑块操作 ==========

    def _scroll_to_top(self) -> None:
        self._slider_scroller.ensure_at_top()

    def _scroll_to_bottom(self) -> int | None:
        """滚动到底部 — 委托给 SliderScroller.scroll_to_bottom()"""
        sr = self._slot_config.slider_region()
        if sr is None:
            return None
        slider_x, slider_top, slider_bottom, slider_w, slider_h = sr

        WindowHelper.focus()
        window = WindowHelper.find_genshin_window()
        result = self._capture.capture(window=window)
        if result is None:
            return None
        slider_y, _, _, _ = SliderDetector.find_slider(
            result.image,
            slider_x, slider_top, slider_bottom, slider_w, slider_h,
        )
        if slider_y is None:
            log.warning("滚动到底: 未检测到滑块")
            return None
        if slider_y - slider_top > SliderDetector.PROXIMITY:
            log.info("滚动到底: 先回到顶部...")
            self._scroll_to_top()
            result = self._capture.capture(window=window)
            if result is None:
                return None
            slider_y, _, _, _ = SliderDetector.find_slider(
                result.image,
                slider_x, slider_top, slider_bottom, slider_w, slider_h,
            )
            if slider_y is None:
                return None

        return self._slider_scroller.scroll_to_bottom(slider_y)

    # ========== 圣遗物识别 ==========

    def _click_and_recognize_artifact(
        self, cx: int, cy: int, ocr
    ) -> ArtifactInfo | None:
        self._mouse.move_and_click(cx, cy)
        return self._recognize_current_artifact(ocr)

    def _recognize_current_artifact(self, ocr) -> ArtifactInfo | None:
        sleep(0.15)  # 等待游戏详情面板刷新
        window = WindowHelper.find_genshin_window()
        result = self._capture.capture(window=window)
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
        window = WindowHelper.find_genshin_window()
        result = self._capture.capture(window=window)
        if result is None:
            return
        det_result = SlotDetector.detect(result.image, config=self._slot_config)
        self._page_scroller.scroll_to_next_page(
            det_result,
            self._tick_delay_ms,
            self._page_settle_ms,
        )