"""清理策略（DecomposePolicy）的判定与动作 —— 假端口，不需要游戏窗口"""

from __future__ import annotations

from backend.automation.artifact_decomposer import (
    ArtifactDecomposer,
    DecomposePolicy,
)
from backend.automation.sweep import ListSweep
from backend.contracts.sweep import SlotContext
from backend.models.dogfood_rule import DogfoodRule
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


def _context(index: int = 1, *, locked: bool = False) -> SlotContext:
    return SlotContext(
        page=0,
        index=index,
        total=3,
        slot=make_slot(index - 1, locked=locked),
        image=b"detail",
    )


def _policy(*, rules: list, default_action: str = "keep", limit: int = 1000) -> tuple[DecomposePolicy, FakePointer]:
    pointer = FakePointer()
    policy = DecomposePolicy(
        rules=rules,
        default_action=default_action,
        max_per_batch=limit,
        pointer=pointer,
    )
    return policy, pointer


DISCARD_ALL = [DogfoodRule(name="全分解", action="discard", priority=10)]


def test_discard_rule_keeps_selection() -> None:
    policy, pointer = _policy(rules=DISCARD_ALL)
    assert policy.on_artifact(make_artifact(rarity=4), _context(1)) is True
    assert (policy.keep, policy.discard) == (0, 1)
    assert pointer.clicks == []  # 命中 discard → 保持选中，不再点击
    assert policy.reached_limit is False


def test_keep_rule_deselects_by_second_click() -> None:
    policy, pointer = _policy(rules=[], default_action="keep")
    assert policy.on_artifact(make_artifact(rarity=4), _context(1)) is True
    assert (policy.keep, policy.discard) == (1, 0)
    # 反选：再次点击同一格
    assert pointer.clicks == [(make_slot(0).cx, make_slot(0).cy)]


def test_stops_at_batch_limit() -> None:
    policy, _pointer = _policy(rules=DISCARD_ALL, limit=2)
    assert policy.on_artifact(make_artifact(main_stat="生命值"), _context(1)) is True
    assert policy.on_artifact(make_artifact(main_stat="攻击力"), _context(2)) is False
    assert policy.discard == 2
    assert policy.reached_limit is True


def test_limit_is_capped_at_1000() -> None:
    policy, _pointer = _policy(rules=DISCARD_ALL, limit=99999)
    assert policy._limit == 1000


def test_stops_when_locked_artifact_found() -> None:
    policy, _pointer = _policy(rules=DISCARD_ALL)
    assert policy.on_artifact(make_artifact(rarity=5), _context(1, locked=True)) is False
    assert policy.reached_limit is True  # 后面还有内容 → Presenter 可继续下一批


def test_mixed_rules_drive_selection() -> None:
    rules = [
        DogfoodRule(name="五星保留", action="keep", main_stat="生命值", priority=10),
        DogfoodRule(name="其余分解", action="discard", priority=1),
    ]
    policy, pointer = _policy(rules=rules)
    policy.on_artifact(make_artifact(main_stat="生命值"), _context(1))  # keep → 反选
    policy.on_artifact(make_artifact(main_stat="攻击力"), _context(2))  # discard → 保持
    assert (policy.keep, policy.discard) == (1, 1)
    assert len(pointer.clicks) == 1


def test_decompose_policy_drives_list_sweep() -> None:
    """与遍历骨架串起来：选择阶段在假端口上跑完整轮"""
    world = FakeWorld(pages=[[make_slot(0), make_slot(1)], [make_slot(2)]])
    reader = FakeReader(
        results=[
            make_artifact(main_stat="生命值"),
            make_artifact(main_stat="攻击力"),
            make_artifact(main_stat="元素充能效率"),
        ]
    )
    policy, pointer = _policy(rules=DISCARD_ALL, limit=2)
    sweep = ListSweep(
        screen=FakeScreen(frames=[make_frame()] * 10),
        pointer=pointer,
        slot_finder=world,
        reader=reader,
        navigator=world,
        timing=FAST,
    )
    summary = sweep.run(policy=policy)

    assert summary.artifacts_read == 2  # 达到单批上限即停
    assert policy.discard == 2
    assert policy.reached_limit is True
    assert summary.stopped_reason == "policy_stop"


# 清理器自有砖：快速选择结果解析（纯函数）

def test_parse_quick_select_result_pairs_label_and_count() -> None:
    ocr_result = [
        [
            [[[10, 10], [110, 10], [110, 30], [10, 30]], ("1星圣遗物", 0.99)],
            [[[10, 40], [60, 40], [60, 60], [10, 60]], ("1,234", 0.99)],
            [[[10, 70], [110, 70], [110, 90], [10, 90]], ("4星圣遗物", 0.99)],
            [[[10, 100], [60, 100], [60, 120], [10, 120]], ("7", 0.99)],
        ]
    ]
    options = ArtifactDecomposer._parse_quick_select_result(ocr_result, roi_offset=(20, 30))
    assert [(o["star"], o["count"]) for o in options] == [(1, 1234), (4, 7)]
    assert options[0]["label"] == "1星圣遗物"
    assert options[0]["pos"] == (20 + 60, 30 + 20)
    assert options[0]["star"] <= 4


def test_parse_quick_select_result_handles_empty() -> None:
    assert ArtifactDecomposer._parse_quick_select_result(None) == []
    assert ArtifactDecomposer._parse_quick_select_result([]) == []
    assert ArtifactDecomposer._parse_quick_select_result([None]) == []
