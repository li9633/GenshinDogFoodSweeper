"""狗粮规则引擎的判定契约（锁定/分解两个功能共用，行为必须钉住）"""

from __future__ import annotations

from backend.automation.dogfood_rule_engine import DogfoodRuleEngine
from backend.models.artifact import ArtifactInfo, ArtifactStat, SubStat
from backend.models.dogfood_rule import DogfoodRule, SubStatCondition


def _artifact(
    *,
    part: str = "生之花",
    set_name: str = "角斗士的终幕礼",
    main_stat: str = "生命值",
    subs: list[tuple[str, float, bool]] | None = None,
    rarity: int = 5,
) -> ArtifactInfo:
    return ArtifactInfo(
        set_name=set_name,
        piece_type=part,
        rarity=rarity,
        main_stat=ArtifactStat(name=main_stat, value=4780.0, is_percentage=False),
        sub_stats=[
            SubStat(name=name, value=value, is_percentage=True, is_activated=activated)
            for name, value, activated in (subs or [])
        ],
    )


def test_priority_order_picks_highest_first() -> None:
    engine = DogfoodRuleEngine(default_action="keep")
    rules = [
        DogfoodRule(name="低优先丢弃", action="discard", priority=1),
        DogfoodRule(name="高优先保留", action="keep", priority=10),
    ]
    assert engine.evaluate(_artifact(), rules) == "keep"


def test_default_action_when_no_rule_matches() -> None:
    engine = DogfoodRuleEngine(default_action="discard")
    rules = [DogfoodRule(name="只认沙上楼阁", action="keep", part="沙上楼阁")]
    assert engine.evaluate(_artifact(), rules) == "discard"


def test_part_and_exclude_filters() -> None:
    engine = DogfoodRuleEngine()
    assert engine.match(_artifact(part="生之花"), DogfoodRule(name="命", part="生之花"))
    assert not engine.match(_artifact(part="死之羽"), DogfoodRule(name="命", part="生之花"))
    assert not engine.match(
        _artifact(part="生之花"),
        DogfoodRule(name="排除", part="*", part_exclude="生之花"),
    )


def test_set_name_is_substring_match() -> None:
    engine = DogfoodRuleEngine()
    assert engine.match(_artifact(set_name="角斗士的终幕礼"), DogfoodRule(name="套", set_name="角斗士"))
    assert not engine.match(_artifact(set_name="追忆之注连"), DogfoodRule(name="套", set_name="角斗士"))


def test_main_stat_must_equal() -> None:
    engine = DogfoodRuleEngine()
    assert engine.match(_artifact(main_stat="生命值"), DogfoodRule(name="主", main_stat="生命值"))
    assert not engine.match(_artifact(main_stat="攻击力"), DogfoodRule(name="主", main_stat="生命值"))


def test_sub_stats_threshold_and_operator() -> None:
    engine = DogfoodRuleEngine()
    artifact = _artifact(subs=[("暴击率", 7.8, True), ("暴击伤害", 14.0, True)])
    rule = DogfoodRule(
        name="双爆",
        sub_stats=[SubStatCondition(name="暴击率", op=">=", value=5.0), SubStatCondition(name="暴击伤害")],
        sub_count=2,
    )
    assert engine.match(artifact, rule)

    too_strict = DogfoodRule(
        name="双爆严格",
        sub_stats=[SubStatCondition(name="暴击率", op=">", value=10.0), SubStatCondition(name="暴击伤害")],
        sub_count=2,
    )
    assert not engine.match(artifact, too_strict)


def test_unactivated_subs_can_be_ignored() -> None:
    engine = DogfoodRuleEngine()
    artifact = _artifact(subs=[("暴击率", 7.8, False)])
    rule = DogfoodRule(
        name="只看已激活",
        sub_stats=[SubStatCondition(name="暴击率")],
        sub_count=1,
        include_unactivated=False,
    )
    assert not engine.match(artifact, rule)

    rule_include = DogfoodRule(
        name="含未激活",
        sub_stats=[SubStatCondition(name="暴击率")],
        sub_count=1,
        include_unactivated=True,
    )
    assert engine.match(artifact, rule_include)


def test_main_stat_can_count_towards_sub_stats() -> None:
    engine = DogfoodRuleEngine()
    artifact = _artifact(main_stat="暴击率", subs=[])
    rule = DogfoodRule(
        name="主词条计入",
        main_stat="*",
        sub_stats=[SubStatCondition(name="暴击率")],
        sub_count=1,
        include_main_stat=True,
    )
    assert engine.match(artifact, rule)
