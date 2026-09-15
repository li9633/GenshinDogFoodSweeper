"""规则卡片/标签文案格式化（QML 只做绑定，文案在这里产出）"""

from __future__ import annotations

from backend.ui.presenters.rule_display import (
    card_display,
    selection_text,
    sub_stat_chip_text,
    with_display,
)


def test_with_display_keeps_raw_fields() -> None:
    rule = {"name": "仅双爆", "priority": 3}
    decorated = with_display(rule)
    assert decorated["name"] == "仅双爆"
    assert decorated["display"] == card_display(rule)


def test_priority_text() -> None:
    assert card_display({"priority": 3})["priority"] == "P3"
    assert card_display({})["priority"] == "P0"


def test_meta_line_hides_wildcards() -> None:
    assert card_display({"part": "*", "main_stat": "*", "set_name": "*"})["meta"] == "任意部位"
    assert (
        card_display(
            {"part": "生之花", "part_exclude": "角斗士", "main_stat": "生命值", "set_name": "追忆"}
        )["meta"]
        == "生之花 · 排除: 角斗士 · 生命值 · 追忆"
    )


def test_sub_stats_line() -> None:
    rule = {
        "sub_stats": [{"name": "暴击率", "op": ">", "value": 7.8}, {"name": "攻击力"}],
        "sub_count": 2,
    }
    assert card_display(rule)["sub_stats"] == "副词条: 暴击率>7.8%, 攻击力  (≥2条匹配)"
    assert card_display({"sub_stats": []})["sub_stats"] == ""
    assert card_display({"sub_stats": [{"name": "暴击率"}]})["sub_stats"] == "副词条: 暴击率"


def test_number_formatting_matches_js_semantics() -> None:
    """7.0 在 JS 里拼成 "7"，Python f-string 会给 "7.0" —— 必须对齐"""
    assert (
        card_display({"sub_stats": [{"name": "暴击率", "op": ">", "value": 7.0}]})["sub_stats"]
        == "副词条: 暴击率>7%"
    )
    assert sub_stat_chip_text({"name": "暴击率", "op": ">", "value": 7.8}) == "暴击率 > 7.8"
    assert sub_stat_chip_text({"name": "攻击力"}) == "攻击力"


def test_selection_text() -> None:
    assert selection_text(0, "选择套装") == "选择套装"
    assert selection_text(3, "选择套装") == "已选 3 个"
    assert selection_text(0, "不限") == "不限"
