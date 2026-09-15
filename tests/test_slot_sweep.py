"""遍历骨架（SlotSweep / ListSweep）与锁定策略的端到端测试

全部使用假端口：不截图、不点击、不需要游戏窗口 —— 这正是抽出遍历骨架的目的。
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from backend.automation.artifact_locker import LockPolicy
from backend.automation.sweep import (
    BaseSweepPolicy,
    ListSweep,
    SlotSweep,
    SweepObserver,
)
from backend.contracts.sweep import SlotContext, SweepSummary, SweepTiming
from backend.models.artifact import ArtifactInfo, ArtifactStat
from backend.models.dogfood_rule import DogfoodRule
from backend.models.slot_models import ArtifactRarity, DetectResult, SlotObject

FAST = SweepTiming(click_delay_s=0.0, detail_settle_s=0.0)


@dataclass
class FakeWorld:
    """模拟"真实列表"：格子内容取决于当前滚动到的页，而不是检测次数"""

    pages: list[list[SlotObject]]
    current: int = 0
    to_top_calls: int = 0
    next_page_calls: int = 0
    find_calls: int = 0

    def find(self, image: object) -> DetectResult:
        self.find_calls += 1
        return DetectResult(slots=list(self.pages[self.current]), bottom_y=0.0, debug_infos=())

    def to_top(self) -> None:
        self.to_top_calls += 1
        self.current = 0

    def next_page(self, det_result: object) -> bool:
        self.next_page_calls += 1
        if self.current + 1 >= len(self.pages):
            return False
        self.current += 1
        return True


@dataclass
class FakeScreen:
    """按脚本依次返回画面；用尽后重复最后一张"""

    frames: list[object]
    calls: int = 0
    prepared: int = 0

    def prepare(self) -> None:
        self.prepared += 1

    def capture(self) -> object | None:
        index = min(self.calls, len(self.frames) - 1)
        self.calls += 1
        return self.frames[index]


@dataclass
class FakePointer:
    clicks: list[tuple[int, int]] = field(default_factory=list)

    def click(self, x: int, y: int) -> None:
        self.clicks.append((x, y))


@dataclass
class FakeReader:
    """按识别次数依次返回结果；None 表示识别失败"""

    results: list[ArtifactInfo | None]
    calls: int = 0

    def read(self, image: object) -> ArtifactInfo | None:
        index = min(self.calls, len(self.results) - 1)
        self.calls += 1
        return self.results[index]


@dataclass
class FakeToggler:
    toggles: list[object] = field(default_factory=list)

    def toggle(self, image: object) -> None:
        self.toggles.append(image)


def _slot(index: int, *, rarity: ArtifactRarity = ArtifactRarity.FIVE, locked: bool = False) -> SlotObject:
    return SlotObject(
        cx=100 + index * 10,
        cy=200,
        x=0,
        y=0,
        w=10,
        h=10,
        rarity=rarity,
        locked=locked,
        row=0,
        col=index,
    )


def _artifact(*, rarity: int = 5, main_stat: str = "生命值") -> ArtifactInfo:
    return ArtifactInfo(
        set_name="角斗士的终幕礼",
        piece_type="生之花",
        rarity=rarity,
        main_stat=ArtifactStat(name=main_stat, value=4780.0, is_percentage=False),
    )


def _build(world: FakeWorld, reader: FakeReader, frames: list[object]):
    screen = FakeScreen(frames=frames)
    pointer = FakePointer()
    sweep = ListSweep(
        screen=screen,
        pointer=pointer,
        slot_finder=world,
        reader=reader,
        navigator=world,
        timing=FAST,
    )
    return sweep, screen, pointer


# ── 单页遍历 ────────────────────────────────────────────────


def test_slot_sweep_visits_every_slot_and_reports_context() -> None:
    slots = [_slot(0), _slot(1), _slot(2)]
    det = DetectResult(slots=slots, bottom_y=0.0, debug_infos=())
    seen: list[tuple[int, int]] = []
    reader = FakeReader(results=[_artifact()] * 3)

    sweep = SlotSweep(
        screen=FakeScreen(frames=[b"detail"]),
        pointer=FakePointer(),
        slot_finder=det,
        reader=reader,
        timing=FAST,
    )
    finished = sweep.run_page(
        det,
        page=0,
        policy=BaseSweepPolicy(),
        # 识别结果会带上扫描位置（页/行/列），便于保存与回查
        observer=SweepObserver(on_artifact=lambda art, ctx: seen.append((ctx.index, art.col))),
    )

    assert finished is True
    assert seen == [(1, 0), (2, 1), (3, 2)]
    assert reader.calls == 3


def test_slot_sweep_prefilter_skips_click_and_read() -> None:
    slots = [_slot(0, locked=True), _slot(1, locked=False)]
    det = DetectResult(slots=slots, bottom_y=0.0, debug_infos=())
    pointer = FakePointer()
    reader = FakeReader(results=[_artifact()])

    class _SkipLocked(BaseSweepPolicy):
        def should_click(self, slot: SlotObject) -> bool:
            return not slot.locked

    sweep = SlotSweep(
        screen=FakeScreen(frames=[b"detail"]),
        pointer=pointer,
        slot_finder=det,
        reader=reader,
        timing=FAST,
    )
    assert sweep.run_page(det, page=0, policy=_SkipLocked()) is True
    assert pointer.clicks == [(110, 200)]  # 只点了未锁定的那一格
    assert reader.calls == 1


def test_slot_sweep_stops_when_policy_returns_false() -> None:
    slots = [_slot(i) for i in range(4)]
    det = DetectResult(slots=slots, bottom_y=0.0, debug_infos=())
    pointer = FakePointer()
    reader = FakeReader(results=[_artifact()] * 4)

    class _StopAfterTwo(BaseSweepPolicy):
        def __init__(self) -> None:
            self.count = 0

        def on_artifact(self, artifact: ArtifactInfo, ctx: SlotContext) -> bool:
            self.count += 1
            return self.count < 2

    sweep = SlotSweep(
        screen=FakeScreen(frames=[b"detail"]),
        pointer=pointer,
        slot_finder=det,
        reader=reader,
        timing=FAST,
    )
    assert sweep.run_page(det, page=0, policy=_StopAfterTwo()) is False
    assert len(pointer.clicks) == 2


def test_slot_sweep_keeps_going_when_reader_fails() -> None:
    slots = [_slot(0), _slot(1)]
    det = DetectResult(slots=slots, bottom_y=0.0, debug_infos=())
    reader = FakeReader(results=[None, _artifact()])

    sweep = SlotSweep(
        screen=FakeScreen(frames=[b"detail"]),
        pointer=FakePointer(),
        slot_finder=det,
        reader=reader,
        timing=FAST,
    )
    assert sweep.run_page(det, page=0, policy=BaseSweepPolicy()) is True
    assert reader.calls == 2


# ── 纯点击模式（调试面板批量点击用的第二种用法） ─────────────


class _ClickOnly(BaseSweepPolicy):
    """只点击：不截图、不识别 —— 连 reader 都不需要"""

    def needs_detail(self) -> bool:
        return False


def test_click_only_policy_skips_capture_and_reader() -> None:
    slots = [_slot(0), _slot(1), _slot(2)]
    det = DetectResult(slots=slots, bottom_y=0.0, debug_infos=())
    screen = FakeScreen(frames=[b"detail"])
    pointer = FakePointer()
    clicked: list[tuple[int, int]] = []

    sweep = SlotSweep(
        screen=screen,
        pointer=pointer,
        slot_finder=det,
        reader=None,  # 纯点击模式不需要识别端口
        timing=FAST,
    )
    finished = sweep.run_page(
        det,
        page=0,
        policy=_ClickOnly(),
        observer=SweepObserver(
            on_slot_clicked=lambda idx, total, _slot: clicked.append((idx, total))
        ),
    )

    assert finished is True
    assert pointer.clicks == [(100, 200), (110, 200), (120, 200)]
    assert screen.calls == 0  # 没有一次多余的截图
    assert clicked == [(1, 3), (2, 3), (3, 3)]


def test_click_only_policy_observes_stop_between_slots() -> None:
    slots = [_slot(i) for i in range(5)]
    det = DetectResult(slots=slots, bottom_y=0.0, debug_infos=())
    pointer = FakePointer()
    flags = {"stop": False}

    def _on_slot_clicked(index: int, _total: int, _slot: SlotObject) -> None:
        if index == 2:
            flags["stop"] = True

    sweep = SlotSweep(
        screen=FakeScreen(frames=[b"detail"]),
        pointer=pointer,
        slot_finder=det,
        reader=None,
        timing=FAST,
    )
    finished = sweep.run_page(
        det,
        page=0,
        policy=_ClickOnly(),
        observer=SweepObserver(on_slot_clicked=_on_slot_clicked),
        stop_check=lambda: flags["stop"],
    )

    assert finished is False
    assert len(pointer.clicks) == 2


def test_slot_sweep_rejects_missing_reader_before_clicking() -> None:
    """装配错误（策略要识别却没给 reader）必须在点击之前暴露"""
    slots = [_slot(0)]
    det = DetectResult(slots=slots, bottom_y=0.0, debug_infos=())
    pointer = FakePointer()
    sweep = SlotSweep(
        screen=FakeScreen(frames=[b"detail"]),
        pointer=pointer,
        slot_finder=det,
        reader=None,
        timing=FAST,
    )

    with pytest.raises(ValueError, match="reader"):
        sweep.run_page(det, page=0, policy=BaseSweepPolicy())
    assert pointer.clicks == []


# ── 整轮遍历 ────────────────────────────────────────────────


def test_list_sweep_pages_until_last_page() -> None:
    world = FakeWorld(pages=[[_slot(0), _slot(1)], [_slot(2), _slot(3)], [_slot(4)]])
    reader = FakeReader(results=[_artifact()] * 8)
    sweep, screen, pointer = _build(world, reader, frames=[b"page"] * 20)

    summary = sweep.run(policy=BaseSweepPolicy())

    assert summary.pages_scanned == 3
    assert summary.artifacts_read == 5
    assert screen.prepared == 1
    assert world.to_top_calls == 1
    assert world.next_page_calls == 3  # 第 3 次返回 False（已是最后一页）
    assert len(pointer.clicks) == 5


def test_list_sweep_respects_total_pages() -> None:
    world = FakeWorld(pages=[[_slot(0)], [_slot(1)], [_slot(2)]])
    reader = FakeReader(results=[_artifact()] * 3)
    sweep, _, _ = _build(world, reader, frames=[b"p"] * 10)

    summary = sweep.run(policy=BaseSweepPolicy(), total_pages=1)

    assert summary.stopped_reason == SweepSummary.PAGE_LIMIT
    assert summary.artifacts_read == 1
    assert world.next_page_calls == 0


def test_list_sweep_stops_on_user_stop() -> None:
    world = FakeWorld(pages=[[_slot(0)], [_slot(1)]])
    reader = FakeReader(results=[_artifact()] * 2)
    sweep, _, _ = _build(world, reader, frames=[b"p"] * 10)

    flags = {"stop": False}

    class _StopAfterFirst(BaseSweepPolicy):
        def on_artifact(self, artifact: ArtifactInfo, ctx: SlotContext) -> bool:
            flags["stop"] = True
            return True

    summary = sweep.run(policy=_StopAfterFirst(), stop_check=lambda: flags["stop"])

    assert summary.stopped_reason == SweepSummary.USER_STOP
    assert summary.artifacts_read == 1


def test_list_sweep_ends_when_no_slots() -> None:
    world = FakeWorld(pages=[[]])
    reader = FakeReader(results=[])
    sweep, _screen, pointer = _build(world, reader, frames=[b"empty"] * 4)

    summary = sweep.run(policy=BaseSweepPolicy())

    assert summary.stopped_reason == SweepSummary.COMPLETED
    assert summary.artifacts_read == 0
    assert pointer.clicks == []
    assert world.next_page_calls == 0  # 没有格子就不翻页


# ── 端口适配器与契约的一致性（构造即验证，不需要游戏窗口） ─────


def test_adapters_satisfy_sweep_contracts() -> None:
    """适配器必须满足契约里的端口 —— 底层原语签名漂移时这条会失败"""
    from backend.automation.sweep_adapters import (
        DetectorSlotFinder,
        LockIconToggler,
        MousePointer,
        RecognizerArtifactReader,
        ScrollerNavigator,
        WindowScreenSource,
    )
    from backend.contracts.sweep import (
        ArtifactReader,
        ListNavigator,
        Pointer,
        ScreenSource,
        SlotFinder,
    )
    from backend.models.slot_models import BAG_SLOT_CONFIG

    config = BAG_SLOT_CONFIG
    assert isinstance(WindowScreenSource(config), ScreenSource)
    assert isinstance(MousePointer(), Pointer)
    assert isinstance(DetectorSlotFinder(config), SlotFinder)
    assert isinstance(RecognizerArtifactReader(config, None), ArtifactReader)
    assert isinstance(ScrollerNavigator(config), ListNavigator)
    LockIconToggler(config).reset()  # 锁定动作不属遍历端口，但构造必须可用


def test_lock_policy_satisfies_sweep_policy() -> None:
    from backend.contracts.sweep import SweepPolicy

    policy = LockPolicy(
        rules=[],
        default_action="keep",
        re_unlock=False,
        max_count=0,
        toggler=FakeToggler(),  # type: ignore[arg-type]
    )
    assert isinstance(policy, SweepPolicy)


# ── 锁定策略（同样不需要游戏） ───────────────────────────────


def test_lock_policy_counts_and_actions() -> None:
    keep_rule = DogfoodRule(name="保留生命值", action="keep", main_stat="生命值", priority=10)
    discard_rule = DogfoodRule(name="其余丢弃", action="discard", priority=1)
    toggler = FakeToggler()
    policy = LockPolicy(
        rules=[keep_rule, discard_rule],
        default_action="keep",
        re_unlock=True,
        max_count=0,
        toggler=toggler,  # type: ignore[arg-type]
    )

    assert policy.should_click(_slot(0, locked=True)) is True  # re_unlock=True 时不跳过已锁

    # 命中 keep → 锁定
    assert policy.on_artifact(_artifact(main_stat="生命值"), SlotContext(0, 1, 2, _slot(0), b"img")) is True
    # 命中 discard 且 re_unlock → 解锁
    assert policy.on_artifact(_artifact(main_stat="攻击力"), SlotContext(0, 2, 2, _slot(1), b"img")) is True
    assert (policy.locked, policy.unlocked, policy.skipped) == (1, 1, 0)
    assert len(toggler.toggles) == 2


def test_lock_policy_skips_discard_when_not_re_unlock() -> None:
    toggler = FakeToggler()
    policy = LockPolicy(
        rules=[DogfoodRule(name="全丢弃", action="discard", priority=1)],
        default_action="discard",
        re_unlock=False,
        max_count=0,
        toggler=toggler,  # type: ignore[arg-type]
    )
    assert policy.on_artifact(_artifact(rarity=4), SlotContext(0, 1, 1, _slot(0), b"img")) is True
    assert (policy.locked, policy.unlocked, policy.skipped) == (0, 0, 1)
    assert toggler.toggles == []
    assert policy.should_click(_slot(0, locked=True)) is False  # 已锁定的格子不点


def test_lock_policy_stops_at_max_count() -> None:
    toggler = FakeToggler()
    policy = LockPolicy(
        rules=[DogfoodRule(name="保留", action="keep", priority=1)],
        default_action="keep",
        re_unlock=False,
        max_count=2,
        toggler=toggler,  # type: ignore[arg-type]
    )
    assert policy.on_artifact(_artifact(), SlotContext(0, 1, 3, _slot(0), b"i")) is True
    assert policy.on_artifact(_artifact(), SlotContext(0, 2, 3, _slot(1), b"i")) is False
    assert policy.processed == 2
