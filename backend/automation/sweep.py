"""逐格遍历引擎（扫描 / 锁定 / 清理三个功能共用）
================================================
原先「定位列表 → 逐格点击 → 读出详情 → 判定 → 动作 → 翻页」这套骨架在
``artifact_scanner`` / ``artifact_locker`` / ``artifact_decomposer`` 里各写了一遍，
这里收敛成两个可组合的单元：

- :class:`SlotSweep` —— **一页**的逐格遍历；
- :class:`ListSweep` —— **一整轮**：准备 → 多页 ``SlotSweep`` → 翻页 → 汇总。

三个功能只提供 :class:`~backend.contracts.sweep.SweepPolicy`（预筛/判定/动作）
与观察回调（日志、进度、事件）。本模块不依赖 Qt、不直接依赖任何底层原语实现，
只依赖契约里的端口 —— 因此可以用假端口写端到端单测。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter, sleep
from typing import Any

from backend.contracts.sweep import (
    ArtifactReader,
    ListNavigator,
    Pointer,
    ScreenSource,
    SlotContext,
    SlotFinder,
    SweepSummary,
    SweepTiming,
)
from backend.models.artifact import ArtifactInfo
from backend.models.slot_models import SlotObject
from backend.utils.logger import log


class BaseSweepPolicy:
    """默认策略：全部点击、全部识别、识别后继续（子类只覆写关心的钩子）"""

    def should_click(self, slot: SlotObject) -> bool:
        return True

    def needs_detail(self) -> bool:
        return True

    def should_read(self, slot: SlotObject, image: Any) -> bool:
        return True

    def on_artifact(self, artifact: ArtifactInfo, ctx: SlotContext) -> bool:
        return True


@dataclass
class SweepObserver:
    """遍历过程回调（默认全是空实现，功能按需覆盖）

    注意 ``on_artifact`` 在**策略判定之前**触发（原始识别事件），
    因此它也会看到随后被策略判为重复而丢弃的结果；
    需要"只统计被采纳的结果"时，用策略自己的回调（如 ``ScanPolicy(on_result=...)``）。
    """

    on_page_start: Callable[[int, int], None] | None = None
    """(page_index, slots_total) 每页开始时"""

    on_slot_clicked: Callable[[int, int, SlotObject], None] | None = None
    """(index, slots_total, slot) 每点完一格（含纯点击模式）；用于逐格进度"""

    on_artifact: Callable[[ArtifactInfo, SlotContext], None] | None = None
    """识别成功一件后（原始事件，早于策略判定）"""

    def page_start(self, page: int, slots_total: int) -> None:
        if self.on_page_start:
            self.on_page_start(page, slots_total)

    def slot_clicked(self, index: int, slots_total: int, slot: SlotObject) -> None:
        if self.on_slot_clicked:
            self.on_slot_clicked(index, slots_total, slot)

    def artifact(self, artifact: ArtifactInfo, ctx: SlotContext) -> None:
        if self.on_artifact:
            self.on_artifact(artifact, ctx)


@dataclass
class _Counters:
    slots_entered: int = 0
    artifacts_read: int = 0


class SlotSweep:
    """一页的逐格遍历

    每格流程：``should_click`` 预筛 → 点击 → 等待详情面板 → 截图 →
    ``should_read`` 检查 → ``ArtifactReader.read`` 识别 → ``on_artifact`` 判定与动作。

    策略声明 ``needs_detail() == False`` 时走**纯点击**路径：点击后直接进下一格
    （不截图、不识别），此时 ``reader`` 可以不传。
    """

    def __init__(
        self,
        *,
        screen: ScreenSource,
        pointer: Pointer,
        slot_finder: SlotFinder,
        reader: ArtifactReader | None = None,
        timing: SweepTiming | None = None,
    ) -> None:
        self._screen = screen
        self._pointer = pointer
        self._slot_finder = slot_finder
        self._reader = reader
        self._timing = timing or SweepTiming()

    def run_page(
        self,
        det_result: Any,
        *,
        page: int,
        policy: Any,
        observer: SweepObserver | None = None,
        stop_check: Callable[[], bool] | None = None,
        counters: _Counters | None = None,
    ) -> bool:
        """遍历一页格子

        Returns:
            False = 需要结束整轮（策略或用户停止）；True = 本页正常结束
        """
        count = counters or _Counters()
        slots: list[SlotObject] = list(getattr(det_result, "slots", []) or [])
        total = len(slots)
        needs_detail = policy.needs_detail()
        if needs_detail and self._reader is None:
            # 策略要识别却没给 reader：属于装配错误，宁可在点击前失败
            raise ValueError("策略需要识别，但 SlotSweep 未提供 reader 端口")
        if observer:
            observer.page_start(page, total)

        for index, slot in enumerate(slots, start=1):
            if stop_check and stop_check():
                return False
            if not policy.should_click(slot):
                continue

            self._pointer.click(slot.cx, slot.cy)
            sleep(self._timing.click_delay_s)
            count.slots_entered += 1
            if observer:
                observer.slot_clicked(index, total, slot)
            if not needs_detail:
                continue

            sleep(self._timing.detail_settle_s)
            image = self._screen.capture()
            if image is None:
                log.warning(f"[P{page + 1}-{index}/{total}] 截图失败，跳过该格")
                continue
            if not policy.should_read(slot, image):
                continue

            artifact = self._reader.read(image)
            if artifact is None:
                log.warning(f"[P{page + 1}-{index}/{total}] 识别失败，跳过")
                continue

            artifact.page = page
            artifact.row = slot.row
            artifact.col = slot.col
            count.artifacts_read += 1

            ctx = SlotContext(
                page=page,
                index=index,
                total=total,
                slot=slot,
                image=image,
                reread=self._reread,
            )
            if observer:
                observer.artifact(artifact, ctx)
            if not policy.on_artifact(artifact, ctx):
                return False

        return True

    def _reread(self) -> ArtifactInfo | None:
        """重新截屏并识别当前格（同一格重复时用于确认详情面板是否真的没刷新）"""
        sleep(self._timing.detail_settle_s)
        image = self._screen.capture()
        if image is None:
            return None
        return self._reader.read(image)


class ListSweep:
    """一整轮列表遍历：准备 → 逐页 → 翻页 → 汇总"""

    def __init__(
        self,
        *,
        screen: ScreenSource,
        pointer: Pointer,
        slot_finder: SlotFinder,
        reader: ArtifactReader,
        navigator: ListNavigator,
        timing: SweepTiming | None = None,
    ) -> None:
        self._screen = screen
        self._pointer = pointer
        self._slot_finder = slot_finder
        self._reader = reader
        self._navigator = navigator
        self._timing = timing or SweepTiming()

    def run(
        self,
        *,
        policy: Any,
        observer: SweepObserver | None = None,
        stop_check: Callable[[], bool] | None = None,
        total_pages: int | None = None,
    ) -> SweepSummary:
        """执行遍历

        Args:
            policy: 策略（预筛 / 判定 / 动作）
            observer: 过程回调
            stop_check: 外部停止检查（用户停止 / 热键）
            total_pages: 已知总页数（扫描器用 OCR 数量算出）；None = 扫到没有格子为止
        """
        counters = _Counters()
        started = perf_counter()

        self._screen.prepare()
        self._navigator.to_top()
        if stop_check and stop_check():
            return self._summary(0, counters, SweepSummary.USER_STOP, started)

        page_sweep = SlotSweep(
            screen=self._screen,
            pointer=self._pointer,
            slot_finder=self._slot_finder,
            reader=self._reader,
            timing=self._timing,
        )

        page = 0
        reason = SweepSummary.COMPLETED
        while True:
            if stop_check and stop_check():
                reason = SweepSummary.USER_STOP
                break
            if total_pages is not None and page >= total_pages:
                reason = SweepSummary.PAGE_LIMIT
                break

            image = self._screen.capture()
            if image is None:
                log.warning(f"第 {page + 1} 页截图失败，结束遍历")
                break
            det_result = self._slot_finder.find(image)
            if not list(getattr(det_result, "slots", []) or []):
                log.info("未检测到格子，遍历结束")
                break

            log.info(f"第 {page + 1} 页检测到 {len(det_result.slots)} 个格子")
            if not page_sweep.run_page(
                det_result,
                page=page,
                policy=policy,
                observer=observer,
                stop_check=stop_check,
                counters=counters,
            ):
                reason = (
                    SweepSummary.USER_STOP
                    if (stop_check and stop_check())
                    else SweepSummary.POLICY_STOP
                )
                break

            page += 1

            if total_pages is not None and page >= total_pages:
                reason = SweepSummary.PAGE_LIMIT
                break
            if stop_check and stop_check():
                reason = SweepSummary.USER_STOP
                break

            # 翻页前重新截图+检测：点击动作会改变列表的选中/滚动状态
            fresh_image = self._screen.capture()
            if fresh_image is None:
                log.warning("翻页前截图失败，结束遍历")
                break
            fresh_det = self._slot_finder.find(fresh_image)
            if not self._navigator.next_page(fresh_det):
                log.info("已是最后一页")
                break

        return self._summary(page, counters, reason, started)

    @staticmethod
    def _summary(
        pages: int,
        counters: _Counters,
        reason: str,
        started: float,
    ) -> SweepSummary:
        elapsed = perf_counter() - started
        log.info(
            f"遍历结束（{reason}）: {pages} 页, 进入 {counters.slots_entered} 格, "
            f"识别 {counters.artifacts_read} 件, 用时 {elapsed:.1f}s"
        )
        return SweepSummary(
            pages_scanned=pages,
            slots_entered=counters.slots_entered,
            artifacts_read=counters.artifacts_read,
            stopped_reason=reason,
        )
