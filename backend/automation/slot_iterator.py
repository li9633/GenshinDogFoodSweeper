"""
圣遗物格子遍历器 — 纯逻辑，无 Qt 依赖
=====================================
统一所有圣遗物批量操作（扫描、锁定、分解）的格子遍历逻辑。
输入 SlotDetector.detect() 的 DetectResult，
对每个格子点击并回调，支持点击前过滤和提前停止。

可在任意上下文中使用：QThread / QObject+QEventLoop / 同步脚本。
"""

from __future__ import annotations

from collections.abc import Callable
from time import sleep

from backend.automation.mouse_controller import MouseController
from backend.models.slot_models import DetectResult, SlotObject


class SlotIterator:
    """圣遗物格子遍历器

    职责：接收 DetectResult，遍历格子，点击并执行用户回调。
    不负责：截图、OCR、规则评估、翻页。
l
    使用方式：
        iterator = SlotIterator(mouse)
        iterator.iter_slots(
            det_result,
            on_slot=lambda slot, idx, total: handle(slot),
            stop_check=lambda: self._stop,
            pre_check=lambda slot: not slot.locked,
        )
    """

    def __init__(self, mouse: MouseController) -> None:
        self._mouse = mouse
        self._stopped = False

    def stop(self) -> None:
        """外部停止：设置标志，iter_slots 将在下一个格子前退出。"""
        self._stopped = True

    def reset(self) -> None:
        """重置停止标志，允许下次遍历。"""
        self._stopped = False

    def iter_slots(
        self,
        det_result: DetectResult,
        on_slot: Callable[[SlotObject, int, int], bool],
        stop_check: Callable[[], bool] | None = None,
        pre_check: Callable[[SlotObject], bool] | None = None,
        click_delay: float = 0.35,
    ) -> bool:
        """遍历当前页所有格子。

        Args:
            det_result: SlotDetector.detect() 的检测结果
            on_slot: 每个格子的回调 (slot, idx, total) -> bool
                     True=继续, False=停止遍历
            stop_check: 外部停止检查 () -> bool，True=停止
            pre_check: 点击前检查 (slot) -> bool，False=跳过此格（不点击）
            click_delay: 点击后等待时间（秒）

        Returns:
            True 正常完成，False 提前停止
        """
        total = len(det_result.slots)
        for idx, slot in enumerate(det_result.slots, start=1):
            if self._stopped:
                return False
            if stop_check and stop_check():
                return False
            if pre_check and not pre_check(slot):
                continue
            self._mouse.move_and_click(slot.cx, slot.cy)
            sleep(click_delay)
            if not on_slot(slot, idx, total):
                return False
        return True
