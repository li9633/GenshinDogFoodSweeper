"""规则卡片展示文案
================
``RuleCard`` 被「规则预设 / 圣遗物锁定 / 圣遗物分解」三个页面共用，
卡片上的文案（优先级、条件行、副词条行）统一在这里拼好，
QML 只做绑定、不拼字符串 —— 与 UpdatePresenter 的 progressLabel 等同一套做法。

三个 Presenter 在构造各自规则 dict 时调用 :func:`with_display` 即可。
"""

from __future__ import annotations

ANY_PART = "任意部位"
ANY_MAIN_STAT = "任意主词条"

_WILDCARD = "*"
_SEGMENT_SEP = " · "
_SUB_STATS_PREFIX = "副词条: "
_SUB_STATS_SEP = ", "


def with_display(rule: dict) -> dict:
    """返回带 ``display`` 展示字段的规则 dict（原始字段保持不变）"""
    return rule | {"display": card_display(rule)}


def card_display(rule: dict) -> dict:
    """规则卡片展示文案：``priority`` / ``meta`` / ``sub_stats``"""
    return {
        "priority": f"P{rule.get('priority') or 0}",
        "meta": _meta_line(rule),
        "sub_stats": _sub_stats_line(rule),
    }


def _meta_line(rule: dict) -> str:
    """条件行：``部位 · 排除: X · 主词条 · 套装``（通配符与空值不展示）"""
    segments = [_part_text(rule.get("part"))]
    exclude = str(rule.get("part_exclude") or "")
    if exclude and exclude != _WILDCARD:
        segments.append(f"排除: {exclude}")
    main_stat = _wildcard_to_empty(rule.get("main_stat"))
    if main_stat:
        segments.append(main_stat)
    set_name = _wildcard_to_empty(rule.get("set_name"))
    if set_name:
        segments.append(set_name)
    return _SEGMENT_SEP.join(segments)


def _sub_stats_line(rule: dict) -> str:
    """副词条行：``副词条: 暴击率>7.8%, 攻击力  (≥2条匹配)``；无条件时返回空串"""
    labels = [
        text
        for text in (
            _sub_stat_text(sub)
            for sub in rule.get("sub_stats") or []
            if isinstance(sub, dict)
        )
        if text
    ]
    if not labels:
        return ""
    line = _SUB_STATS_PREFIX + _SUB_STATS_SEP.join(labels)
    sub_count = rule.get("sub_count") or 0
    if sub_count > 0:
        line += f"  (≥{sub_count}条匹配)"
    return line


def _sub_stat_text(sub: dict) -> str:
    name = str(sub.get("name") or "")
    op = str(sub.get("op") or "")
    value = sub.get("value")
    if op and value:
        return f"{name}{op}{_num(value)}%"
    return name


def _part_text(value: object) -> str:
    text = str(value or "")
    return ANY_PART if text in ("", _WILDCARD) else text


def _wildcard_to_empty(value: object) -> str:
    text = str(value or "")
    return "" if text in ("", _WILDCARD) else text


def _num(value: object) -> str:
    """与 QML/JS 的数字转字符串保持一致（``7.0`` → ``7``，``7.8`` → ``7.8``）"""
    try:
        return f"{float(value):g}"
    except (TypeError, ValueError):
        return str(value)


def sub_stat_chip_text(sub: dict) -> str:
    """已选副词条标签文案，如 ``暴击率 > 7.8``（无条件时只显示词条名）"""
    name = str(sub.get("name") or "")
    op = str(sub.get("op") or "")
    value = sub.get("value")
    if op and value:
        return f"{name} {op} {_num(value)}"
    return name


def selection_text(count: int, empty_text: str) -> str:
    """选择项标签文案：未选中时显示 ``empty_text``，否则显示 ``已选 N 个``"""
    return f"已选 {count} 个" if count else empty_text
