"""狗粮规则评估引擎"""

from __future__ import annotations

from models.artifact import ArtifactInfo
from models.dogfood_rule import DogfoodRule


class DogfoodRuleEngine:
    """按优先级评估规则，命中即停，未命中走默认行为"""

    DEFAULT_ACTION: str = "keep"

    @staticmethod
    def _compare(actual: float, op: str, expected: float) -> bool:
        """值比较，op 为空时仅匹配名称"""
        if op == ">":
            return actual > expected
        if op == "<":
            return actual < expected
        if op == ">=":
            return actual >= expected
        if op == "<=":
            return actual <= expected
        if op == "=":
            return actual == expected
        return True

    @staticmethod
    def match(artifact: ArtifactInfo, rule: DogfoodRule) -> bool:
        """单条规则匹配"""
        if rule.part != "*" and rule.part != artifact.piece_type:
            return False
        if rule.part_exclude and rule.part_exclude == artifact.piece_type:
            return False
        if rule.main_stat != "*" and artifact.main_stat and rule.main_stat != artifact.main_stat.name:
            return False
        if rule.set_name != "*" and artifact.set_name and rule.set_name not in artifact.set_name:
            return False
        if rule.sub_stats:
            matched = 0
            for art_sub in artifact.sub_stats:
                if not art_sub.is_activated:
                    continue
                for rule_sub in rule.sub_stats:
                    if rule_sub.name in art_sub.name:
                        if rule_sub.op and not DogfoodRuleEngine._compare(
                            art_sub.value, rule_sub.op, rule_sub.value
                        ):
                            continue
                        matched += 1
                        break
            if matched < rule.sub_count:
                return False
        return True

    def evaluate(self, artifact: ArtifactInfo, rules: list[DogfoodRule]) -> bool:
        """返回 True=狗粮，按优先级+启用状态评估，命中即停"""
        active = sorted(
            [r for r in rules if r.enabled],
            key=lambda r: r.priority,
            reverse=True,
        )
        for rule in active:
            if self.match(artifact, rule):
                return rule.action == "discard"
        return self.DEFAULT_ACTION == "discard"