"""自动锁定/解锁圣遗物

流程骨架复用 :mod:`backend.automation.sweep` 的 ``ListSweep``（与扫描器/清理器共用）：
定位列表 → 逐格点击 → 识别详情 → 规则判定 → 锁定/解锁 → 翻页。

本模块只负责**差异部分**：:class:`LockPolicy`（预筛 + 规则判定 + 锁定动作 + 计数）。
截图/点击/检测/识别/滚动都由 ``sweep_adapters`` 里的端口适配器接到底层原语上，
其中 ``SlotDetector`` / ``PageScroller`` / ``SliderScroller`` 属冻结模块，只调用不改。
"""

from __future__ import annotations

import threading
from typing import Any

from PySide6.QtCore import QObject, QThread, Signal

from backend.automation.dogfood_rule_engine import DogfoodRuleEngine
from backend.automation.sweep import BaseSweepPolicy, ListSweep, SweepObserver
from backend.automation.sweep_adapters import (
    DetectorSlotFinder,
    LockIconToggler,
    MousePointer,
    RecognizerArtifactReader,
    ScrollerNavigator,
    WindowScreenSource,
)
from backend.contracts.sweep import SlotContext, SweepTiming
from backend.models.artifact import ArtifactInfo
from backend.models.slot_models import BAG_SLOT_CONFIG, SlotObject
from backend.utils.logger import log

# 锁定流程原先依赖旧的逐格遍历器的点击间隔来等待详情面板，现由遍历骨架的
# SweepTiming.click_delay_s 承担，这里不再额外等待
_LOCK_TIMING = SweepTiming(detail_settle_s=0.0)


class LockPolicy(BaseSweepPolicy):
    """锁定策略：规则判定 + 锁定/解锁动作 + 计数与停止条件"""

    def __init__(
        self,
        *,
        rules: list,
        default_action: str,
        re_unlock: bool,
        max_count: int,
        toggler: LockIconToggler,
    ) -> None:
        self._engine = DogfoodRuleEngine(default_action=default_action)
        self._rules = rules
        self._re_unlock = re_unlock
        self._max_count = max_count
        self._toggler = toggler
        self.locked = 0
        self.unlocked = 0
        self.skipped = 0

    @property
    def processed(self) -> int:
        return self.locked + self.unlocked + self.skipped

    def should_click(self, slot: SlotObject) -> bool:
        """``re_unlock=False`` 时跳过已锁定格子（``SlotDetector`` 已预判锁定状态，省一次点击+OCR）"""
        return self._re_unlock or not slot.locked

    def on_artifact(self, artifact: ArtifactInfo, ctx: SlotContext) -> bool:
        action = self._engine.evaluate(artifact, self._rules)

        if action == "keep":
            self._toggler.toggle(ctx.image)
            self.locked += 1
            self._log(ctx, "锁定", artifact)
        elif action == "discard" and self._re_unlock:
            self._toggler.toggle(ctx.image)
            self.unlocked += 1
            self._log(ctx, "解锁", artifact)
        else:
            self.skipped += 1
            log.debug(f"[P{ctx.page + 1}-{ctx.index}/{ctx.total}] → 跳过")

        if self._max_count > 0 and self.processed >= self._max_count:
            log.info(f"已达到最大处理数量 {self._max_count}，停止")
            return False
        return True

    @staticmethod
    def _log(ctx: SlotContext, action: str, artifact: ArtifactInfo) -> None:
        log.info(
            f"[P{ctx.page + 1}-{ctx.index}/{ctx.total}] → {action} "
            f"(套装={artifact.set_name or '?'} "
            f"部位={artifact.piece_type or '?'} "
            f"星级={artifact.rarity or '?'})"
        )


class ArtifactLocker(QObject):
    """自动锁定/解锁圣遗物"""

    def __init__(self) -> None:
        super().__init__()
        self._stop_event = threading.Event()

    def stop(self) -> None:
        """线程安全：设置停止标志，遍历在每个检查点退出"""
        self._stop_event.set()
        log.debug("停止标志已设置")

    def reset_stop(self) -> None:
        self._stop_event.clear()

    def lock_artifacts(
        self,
        rules: list,
        default_action: str,
        re_unlock: bool = False,
        max_count: int = 0,
        ocr: Any = None,
    ) -> tuple[int, int, int]:
        """执行锁定/解锁流程。

        Args:
            rules: 启用的规则列表
            default_action: 默认行为（"keep" 或 "discard"）
            re_unlock: 是否将已锁定的圣遗物重新解锁
            max_count: 最大处理数量，0 表示处理到停止
            ocr: OcrEngine.create_ocr() 返回的 OCR 实例

        Returns:
            (locked_count, unlocked_count, skipped_count)
        """
        self.reset_stop()
        config = BAG_SLOT_CONFIG
        policy = LockPolicy(
            rules=rules,
            default_action=default_action,
            re_unlock=re_unlock,
            max_count=max_count,
            toggler=LockIconToggler(config),
        )
        sweep = ListSweep(
            screen=WindowScreenSource(config),
            pointer=MousePointer(),
            slot_finder=DetectorSlotFinder(config),
            reader=RecognizerArtifactReader(config, ocr),
            navigator=ScrollerNavigator(config),
            timing=_LOCK_TIMING,
        )
        summary = sweep.run(
            policy=policy,
            stop_check=self._stop_event.is_set,
            observer=SweepObserver(on_page_start=_log_page),
        )
        log.info(
            f"锁定流程结束（{summary.stopped_reason}）: "
            f"锁定 {policy.locked} 件, 解锁 {policy.unlocked} 件, 跳过 {policy.skipped} 件"
        )
        return (policy.locked, policy.unlocked, policy.skipped)


def _log_page(page: int, slots_total: int) -> None:
    log.info(f"--- 第 {page + 1} 页（检测到 {slots_total} 个格子）---")


class LockWorker(QThread):
    """后台线程：圣遗物锁定/解锁

    结果信号命名为 ``lockCompleted``，**不覆盖** ``QThread.finished`` ——
    后者由 WorkerHost 用来做线程结束后的清理。
    """

    stepChanged = Signal(str)
    lockCompleted = Signal(int, int, int)
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
            from backend.exceptions.automation import (
                LockIconNotFoundError,
                OcrModelNotReadyError,
            )

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
            self.lockCompleted.emit(locked, unlocked, skipped)

        except OcrModelNotReadyError:
            self.errorOccurred.emit(OcrModelNotReadyError._MESSAGE)
        except LockIconNotFoundError:
            # 异常只承载消息；这里必须上报，否则界面会一直停在"锁定中"
            self.errorOccurred.emit(LockIconNotFoundError._MESSAGE)
        except Exception:
            import traceback

            tb = traceback.format_exc()
            log.error(f"锁定流程发生未知错误:\n{tb}")
            self.errorOccurred.emit("发生未知错误，请查看日志")
