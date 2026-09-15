"""扫描策略（ScanPolicy）的判定逻辑 —— 假端口，不需要游戏窗口"""

from __future__ import annotations

import pytest

from backend.automation.anchor_locator import AnchorLocator
from backend.automation.artifact_scanner import ScanPolicy
from backend.automation.scan_stop_policy import StopPolicy
from backend.automation.sweep import ListSweep, SweepObserver
from backend.contracts.sweep import SlotContext
from backend.models.scan_models import StopMode, StopReason
from backend.models.slot_models import ArtifactRarity
from tests.fakes import (
    FAST,
    FakePointer,
    FakeReader,
    FakeScreen,
    FakeWorld,
    make_artifact,
    make_frame,
    make_slot,
)


def _context(index: int = 1, *, reread=None, slot=None) -> SlotContext:
    return SlotContext(
        page=0,
        index=index,
        total=3,
        slot=slot or make_slot(index - 1),
        image=b"detail",
        reread=reread,
    )


def _policy(**overrides) -> ScanPolicy:
    kwargs = {
        "stop_policy": StopPolicy(StopMode.ANCHOR, dedup_enabled=True),
        "tail_info": None,
        "bag_count": 0,
        "on_result": None,
    }
    kwargs.update(overrides)
    return ScanPolicy(**kwargs)


# 预筛

def test_five_star_mode_skips_non_five_star_slots() -> None:
    policy = _policy(stop_policy=StopPolicy(StopMode.FIVE_STAR_ONLY))
    assert policy.should_click(make_slot(0, rarity=ArtifactRarity.FIVE)) is True
    assert policy.should_click(make_slot(1, rarity=ArtifactRarity.FOUR)) is False


def test_anchor_mode_clicks_every_slot() -> None:
    policy = _policy(stop_policy=StopPolicy(StopMode.ANCHOR))
    assert policy.should_click(make_slot(0, rarity=ArtifactRarity.FOUR)) is True


def test_empty_slot_is_not_read(monkeypatch: pytest.MonkeyPatch) -> None:
    policy = _policy()
    monkeypatch.setattr(AnchorLocator, "is_empty_slot", staticmethod(lambda *_: True))
    assert policy.should_read(make_slot(0), b"grid") is False
    monkeypatch.setattr(AnchorLocator, "is_empty_slot", staticmethod(lambda *_: False))
    assert policy.should_read(make_slot(0), b"grid") is True


# 结果收集与停止条件

def test_collects_results_and_reports_to_callback() -> None:
    collected: list[str] = []
    policy = _policy(on_result=lambda artifact, ctx: collected.append(artifact.main_stat.name))

    assert policy.on_artifact(make_artifact(main_stat="生命值"), _context(1)) is True
    assert policy.on_artifact(make_artifact(main_stat="攻击力"), _context(2)) is True

    assert [a.main_stat.name for a in policy.results] == ["生命值", "攻击力"]
    assert collected == ["生命值", "攻击力"]
    assert policy.stop_reason is None


def test_records_scanned_position_on_artifact() -> None:
    """位置（页/行/列）由遍历骨架写入，策略不改写 —— 端到端见下一条"""
    policy = _policy()
    policy.on_artifact(make_artifact(), _context(3))
    assert policy.results[0].page == 0  # 骨架未参与时保持默认值，说明策略没有越权改写


def test_five_star_mode_drops_non_five_star_results() -> None:
    policy = _policy(stop_policy=StopPolicy(StopMode.FIVE_STAR_ONLY))
    assert policy.on_artifact(make_artifact(rarity=4), _context(1)) is True
    assert policy.results == []


def test_stops_when_fixed_count_reached() -> None:
    policy = _policy(
        stop_policy=StopPolicy(StopMode.FIXED_COUNT, fixed_count=2),
        bag_count=10,
    )
    assert policy.on_artifact(make_artifact(main_stat="生命值"), _context(1)) is True
    assert policy.on_artifact(make_artifact(main_stat="攻击力"), _context(2)) is False
    assert policy.stop_reason is StopReason.FIXED_COUNT
    assert len(policy.results) == 2


def test_stops_when_bag_count_reached() -> None:
    policy = _policy(bag_count=1)
    assert policy.on_artifact(make_artifact(), _context(1)) is False
    assert policy.stop_reason is StopReason.BAG_COUNT


def test_stops_on_tail_anchor_material() -> None:
    tail = make_artifact(main_stat="攻击力")  # 与后续读到的"同一件"重复
    policy = _policy(tail_info=tail)
    assert policy.on_artifact(make_artifact(main_stat="攻击力"), _context(1)) is False
    assert policy.stop_reason is StopReason.TAIL_ANCHOR
    assert policy.results == []  # 尾锚点本身不计入结果


# 去重

def test_duplicate_at_another_position_is_skipped() -> None:
    policy = _policy(stop_policy=StopPolicy(StopMode.FIVE_STAR_ONLY, dedup_enabled=True))
    first = make_artifact(sub_values=(7.8,))
    policy.on_artifact(first, _context(1))
    # 与第一件完全相同 → 判定为重复，且位置不同 → 跳过
    assert policy.on_artifact(make_artifact(sub_values=(7.8,)), _context(2)) is True
    assert len(policy.results) == 1
    assert policy.dedup_skipped == 1


def test_same_position_duplicate_triggers_reread() -> None:
    policy = _policy(stop_policy=StopPolicy(StopMode.FIVE_STAR_ONLY, dedup_enabled=True))
    policy.on_artifact(make_artifact(sub_values=(7.8,)), _context(1))

    reread_calls = {"n": 0}
    fresh = make_artifact(main_stat="攻击力", sub_values=(5.0,))

    def reread():
        reread_calls["n"] += 1
        return fresh

    # 同一格（page/row/col 相同）重复 → 走重识别分支
    same_slot = make_slot(0)
    ctx = SlotContext(0, 1, 3, same_slot, b"img", reread=reread)
    first = policy.results[0]
    first.page, first.row, first.col = 0, same_slot.row, same_slot.col

    assert policy.on_artifact(make_artifact(sub_values=(7.8,)), ctx) is True
    assert reread_calls["n"] == 1
    assert policy.results[-1] is fresh


def test_dedup_disabled_keeps_duplicates() -> None:
    policy = _policy(stop_policy=StopPolicy(StopMode.FIVE_STAR_ONLY, dedup_enabled=False))
    policy.on_artifact(make_artifact(sub_values=(7.8,)), _context(1))
    policy.on_artifact(make_artifact(sub_values=(7.8,)), _context(2))
    assert len(policy.results) == 2
    assert policy.dedup_skipped == 0


# 与遍历骨架串起来（端到端，仍是假端口）

def test_scan_policy_drives_list_sweep() -> None:
    world = FakeWorld(pages=[[make_slot(0), make_slot(1)], [make_slot(2)]])
    reader = FakeReader(
        results=[
            make_artifact(main_stat="生命值"),
            make_artifact(main_stat="攻击力"),
            make_artifact(main_stat="元素充能效率"),
        ]
    )
    policy = _policy(bag_count=3)
    sweep = ListSweep(
        screen=FakeScreen(frames=[make_frame()] * 10),
        pointer=FakePointer(),
        slot_finder=world,
        reader=reader,
        navigator=world,
        timing=FAST,
    )
    summary = sweep.run(policy=policy, observer=SweepObserver(), total_pages=2)

    assert summary.artifacts_read == 3
    assert len(policy.results) == 3
    assert policy.stop_reason is StopReason.BAG_COUNT
    assert summary.stopped_reason == "policy_stop"
    # 遍历骨架负责写入扫描位置（页/行/列），保存格式据此回查
    assert [(a.page, a.row, a.col) for a in policy.results] == [
        (0, 0, 0),
        (0, 0, 1),
        (1, 0, 2),  # 第 2 页那一格在检测结果里的列号
    ]
