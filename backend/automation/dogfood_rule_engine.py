"""狗粮规则评估引擎"""

from __future__ import annotations

from models.artifact import ArtifactInfo
from models.dogfood_rule import DogfoodRule
from utils.logger import log


class DogfoodRuleEngine:
    """按优先级评估规则，命中即停，未命中走默认行为"""

    def __init__(self, default_action: str = "keep"):
        self.DEFAULT_ACTION = default_action

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
        log.debug(
            f"[规则匹配] [{rule.name}] priority={rule.priority} action={rule.action} "
            f"| 圣遗物: 部位={artifact.piece_type} "
            f"主词条={artifact.main_stat.name if artifact.main_stat else '?'} "
            f"套装={artifact.set_name}"
        )

        if rule.part != "*" and rule.part != artifact.piece_type:
            log.debug(
                f"  [{rule.name}] X 部位不匹配: 要求={rule.part} "
                f"实际={artifact.piece_type}"
            )
            return False
        if rule.part_exclude and rule.part_exclude == artifact.piece_type:
            log.debug(
                f"  [{rule.name}] X 部位被排除: {rule.part_exclude}"
            )
            return False
        if rule.main_stat != "*" and artifact.main_stat and rule.main_stat != artifact.main_stat.name:
            log.debug(
                f"  [{rule.name}] X 主词条不匹配: 要求={rule.main_stat} "
                f"实际={artifact.main_stat.name}"
            )
            return False
        if rule.set_name != "*" and artifact.set_name and rule.set_name not in artifact.set_name:
            log.debug(
                f"  [{rule.name}] X 套装不匹配: 要求包含={rule.set_name} "
                f"实际={artifact.set_name}"
            )
            return False
        if rule.sub_stats:
            matched = 0
            for art_sub in artifact.sub_stats:
                if not rule.include_unactivated and not art_sub.is_activated:
                    continue
                for rule_sub in rule.sub_stats:
                    if rule_sub.name in art_sub.name:
                        if rule_sub.op and not DogfoodRuleEngine._compare(
                            art_sub.value, rule_sub.op, rule_sub.value
                        ):
                            continue
                        matched += 1
                        break
            if matched < rule.sub_count and rule.include_main_stat and artifact.main_stat:
                for rule_sub in rule.sub_stats:
                        if rule_sub.name in artifact.main_stat.name:
                            matched += 1
                            break
            if matched < rule.sub_count:
                log.debug(
                    f"  [{rule.name}] X 副词条不足: 匹配{matched}条 "
                    f"要求≥{rule.sub_count}条"
                )
                return False
            log.debug(
                f"  [{rule.name}] ✓ 副词条满足: {matched}/{rule.sub_count}"
            )
        log.info(f"  ✓ 规则命中 [{rule.name}] → {rule.action}")
        return True

    def evaluate(self, artifact: ArtifactInfo, rules: list[DogfoodRule]) -> bool:
        """返回 True=狗粮，按优先级评估，命中即停。

        所有传入的规则均视为已激活（启用由调用方通过规则选择控制）。
        """
        active = sorted(rules, key=lambda r: r.priority, reverse=True)
        log.debug(
            f"[评估] 圣遗物: {artifact.piece_type} | {artifact.set_name} | "
            f"{artifact.main_stat.name if artifact.main_stat else '?'} | "
            f"星级={artifact.rarity} | 规则数={len(active)} "
            f"(按优先级: {[r.name for r in active]})"
        )
        for i, rule in enumerate(active):
            log.debug(f"[评估] 尝试规则 {i + 1}/{len(active)}: [{rule.name}]")
            if self.match(artifact, rule):
                result = rule.action == "discard"
                log.info(f"[评估结果] → {rule.action} (命中规则: {rule.name})")
                return result
        log.info(f"[评估结果] → {self.DEFAULT_ACTION} (未命中任何规则，走默认行为)")
        return self.DEFAULT_ACTION == "discard"