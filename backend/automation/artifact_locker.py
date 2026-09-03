"""自动锁定/解锁圣遗物模块

流程与分解流程基本一致：
1. 截图 → SlotDetector 检测格子
2. 遍历每个格子: 点击打开详情 → OCR 识别 → 规则评估
   - 命中 keep 规则 → 锁定
   - 命中 discard 规则 → 解锁
3. PageScroller 翻页 → 回到步骤 1
4. 无格子时停止
"""

from __future__ import annotations

import threading
import time

import numpy as np
from PySide6.QtCore import QObject, QThread, Signal
from utils.logger import log

from backend.automation.mouse_controller import MouseController
from backend.automation.slot_iterator import SlotIterator
from backend.automation.template_manager import TemplateManager
from backend.automation.template_matcher import multi_scale_match
from backend.automation.window_helper import WindowHelper
from backend.exceptions.automation.exceptions import LockIconNotFoundError
from backend.utils.screen_capture import ScreenshotCapture


class ArtifactLocker(QObject):
    """自动锁定/解锁圣遗物"""

    def __init__(self) -> None:
        super().__init__()
        self._capture = ScreenshotCapture()
        self._stop_event = threading.Event()
        self._fatal_error: str | None = None
        self._lock_icon_center: tuple[int, int] | None = None

    def stop(self) -> None:
        self._stop_event.set()
        log.debug("停止标志已设置")

    def reset_stop(self) -> None:
        self._stop_event.clear()
        self._fatal_error = None
        self._lock_icon_center = None

    # ========== 入口 ==========

    def lock_artifacts(
        self,
        rules: list,
        default_action: str,
        re_unlock: bool = False,
        max_count: int = 0,
        ocr=None,
    ) -> tuple[int, int, int]:
        """执行锁定/解锁流程。

        Args:
            rules: 启用的规则列表
            default_action: 默认行为 ("keep" 或 "discard")
            re_unlock: 是否将已锁定的圣遗物重新解锁
            max_count: 最大处理数量，0 表示处理到停止
            ocr: OcrEngine.create_ocr() 返回的 OCR 实例

        Returns:
            (locked_count, unlocked_count, skipped_count)
        """
        return self._lock_loop(rules, default_action, re_unlock, max_count, ocr)

    # ========== 主循环 ==========

    def _lock_loop(
        self,
        rules: list,
        default_action: str,
        re_unlock: bool,
        max_count: int,
        ocr=None,
    ) -> tuple[int, int, int]:
        """逐格点击 → OCR识别 → 规则评估 → 锁定/解锁 → 翻页。"""
        from backend.automation.dogfood_rule_engine import DogfoodRuleEngine
        from backend.automation.page_scroller import PageScroller
        from backend.automation.slot_detector import SlotDetector
        from backend.models.slot_models import BAG_SLOT_CONFIG

        config = BAG_SLOT_CONFIG
        scroller = PageScroller(MouseController(), self._capture, config)
        engine = DogfoodRuleEngine(default_action=default_action)

        total_locked = 0
        total_unlocked = 0
        total_skipped = 0
        page = 0

        WindowHelper.focus()
        MouseController.set_origin(WindowHelper.get_origin())
        iterator = SlotIterator(MouseController())

        while True:
            if self._stop_event.is_set():
                log.info("收到停止信号，退出锁定循环")
                break

            page += 1
            log.info(f"--- 第 {page} 页 ---")

            window = WindowHelper.find_genshin_window()
            result = self._capture.capture(window=window)
            if result is None:
                log.warning("截图失败")
                break

            det_result = SlotDetector.detect(result.image, config=config)
            if not det_result.slots:
                log.info("未检测到格子，锁定流程结束")
                break

            log.info(
                f"第 {page} 页检测到 {len(det_result.slots)} 个格子"
                f" | 累计: 锁定 {total_locked} 件, 解锁 {total_unlocked} 件, "
                f"跳过 {total_skipped} 件"
            )

            # re_unlock=False 时跳过已锁定格子（SlotDetector 预检测，无需点击+OCR）
            pre_check = (lambda s: not s.locked) if not re_unlock else None

            def on_slot(slot, idx, total, _page=page, _window=window):
                nonlocal total_locked, total_unlocked, total_skipped

                t_start = time.perf_counter()
                log.debug(f"[{_page}-{idx}/{total}] 点击格子 ({slot.cx}, {slot.cy})")

                # 截图并 OCR 识别圣遗物详情（直接同步调用）
                cap_result = self._capture.capture(window=_window)

                artifact = ArtifactLocker._recognize_artifact(
                    cap_result.image, config, ocr
                )
                if artifact is None:
                    log.warning(f"[{_page}-{idx}] OCR 识别失败，跳过")
                    total_skipped += 1
                    return True

                # 规则评估
                action = engine.evaluate(artifact, rules)
                item_time = time.perf_counter() - t_start

                if action == "keep":
                    # 需要锁定
                    self._toggle_lock(cap_result.image)
                    total_locked += 1
                    log.info(
                        f"[{_page}-{idx}/{total}] → 锁定 "
                        f"(套装={artifact.set_name or '?'} "
                        f"部位={artifact.piece_type or '?'} "
                        f"星级={artifact.rarity or '?'}) "
                        f"| 耗时={item_time:.2f}s"
                    )
                elif action == "discard":
                    # 需要解锁（仅 re_unlock 模式才执行）
                    if re_unlock:
                        self._toggle_lock(cap_result.image)
                        total_unlocked += 1
                        log.info(
                            f"[{_page}-{idx}/{total}] → 解锁 "
                            f"(套装={artifact.set_name or '?'} "
                            f"部位={artifact.piece_type or '?'} "
                            f"星级={artifact.rarity or '?'}) "
                            f"| 耗时={item_time:.2f}s"
                        )
                    else:
                        total_skipped += 1
                        log.debug(
                            f"[{_page}-{idx}/{total}] → 跳过(已是锁定状态) "
                            f"| 耗时={item_time:.2f}s"
                        )
                else:
                    total_skipped += 1
                    log.debug(
                        f"[{_page}-{idx}/{total}] → 跳过(默认保留) "
                        f"| 耗时={item_time:.2f}s"
                    )

                # 检查是否达到最大处理数量
                if (
                    max_count > 0
                    and (total_locked + total_unlocked + total_skipped) >= max_count
                ):
                    log.info(f"已达到最大处理数量 {max_count}，停止")
                    return False

                return True

            iterator.reset()
            iterator.iter_slots(
                det_result,
                on_slot=on_slot,
                stop_check=lambda: self._stop_event.is_set(),
                pre_check=pre_check,
            )

            if self._stop_event.is_set():
                break

            # 翻页：截图+检测 → 翻页
            window = WindowHelper.find_genshin_window()
            result = self._capture.capture(window=window)
            det_result = SlotDetector.detect(result.image, config=config)
            if not scroller.scroll_to_next_page(det_result):
                log.info("已是最后一页")
                break

        return (total_locked, total_unlocked, total_skipped)

    # ========== 圣遗物详情 OCR 识别（直接同步调用） ==========

    @staticmethod
    def _recognize_artifact(image: np.ndarray, config, ocr) -> object | None:
        """直接同步 OCR 识别圣遗物详情（在工作线程中调用）。

        Args:
            image: 截图
            config: BAG_SLOT_CONFIG
            ocr: OcrEngine.create_ocr() 返回的 OCR 实例

        Returns:
            ArtifactInfo | None
        """
        from backend.automation.recognizer import ArtifactRecognizer

        try:
            return ArtifactRecognizer.recognize(
                image,
                config.detail_roi_configs,
                ocr,
                lock_anchor_search_region=config.lock_anchor_search_region,
                lock_anchor_to_level=config.lock_anchor_to_level,
                lock_anchor_to_sub_stats=config.lock_anchor_to_sub_stats,
            )
        except Exception as e:
            log.debug(f"[锁定OCR] 识别异常: {e}")
            return None

    # ========== 锁定/解锁操作 ==========

    def _toggle_lock(self, image: np.ndarray) -> None:
        """点击锁定图标切换锁定/解锁状态。

        通过模板匹配找到锁定图标位置并点击。
        首次匹配成功后缓存坐标，后续直接复用。
        """
        if self._lock_icon_center is not None:
            MouseController.move_and_click(*self._lock_icon_center)
            time.sleep(0.3)
            return

        template = TemplateManager.get("锁定图标")
        if template is None:
            log.error("未找到模板: 锁定图标")
            raise LockIconNotFoundError("锁定图标模板未加载")

        score, (rel_x, rel_y), scale, (_w, _h) = multi_scale_match(image, template)
        if score < 0.80:
            log.warning(f"锁定图标匹配失败: 得分={score:.3f}")
            raise LockIconNotFoundError(f"锁定图标匹配得分过低: {score:.3f}")

        abs_x, abs_y = WindowHelper.to_absolute(rel_x, rel_y)
        win_origin = WindowHelper.get_origin()
        log.info(
            f"锁定图标匹配成功: 得分={score:.3f} 缩放={scale:.2f} "
            f"窗口相对=({rel_x}, {rel_y}) 窗口原点={win_origin} "
            f"屏幕绝对=({abs_x}, {abs_y})"
        )

        self._lock_icon_center = (rel_x, rel_y)
        MouseController.move_and_click(rel_x, rel_y)
        time.sleep(0.3)


# ====================================================================
# 锁定 Worker（后台线程）
# ====================================================================


class LockWorker(QThread):
    """后台线程：圣遗物锁定/解锁"""

    stepChanged = Signal(str)
    finished = Signal(int, int, int)
    errorOccurred = Signal(str)

    def __init__(
        self,
        locker: ArtifactLocker,
        rules: list,
        default_action: str,
        re_unlock: bool,
        max_count: int,
        engines_dir=None,
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self._locker = locker
        self._rules = rules
        self._default_action = default_action
        self._re_unlock = re_unlock
        self._max_count = max_count
        self._engines_dir = engines_dir

    def stop(self) -> None:
        self._locker.stop()

    def run(self) -> None:
        try:
            from backend.automation.ocr_engine import OcrEngine
            from backend.exceptions.automation import OcrModelNotReadyError

            self.stepChanged.emit("正在初始化 OCR 引擎...")
            ocr = OcrEngine.create_ocr(self._engines_dir)

            self.stepChanged.emit("正在锁定/解锁圣遗物...")
            locked, unlocked, skipped = self._locker.lock_artifacts(
                self._rules,
                self._default_action,
                self._re_unlock,
                self._max_count,
                ocr,
            )

            if self._locker._fatal_error:
                self.errorOccurred.emit(self._locker._fatal_error)
                return

            self.finished.emit(locked, unlocked, skipped)

        except OcrModelNotReadyError:
            self.errorOccurred.emit(OcrModelNotReadyError._MESSAGE)
        except Exception as e:
            import traceback

            self.errorOccurred.emit(f"{e}\n{traceback.format_exc()}")
