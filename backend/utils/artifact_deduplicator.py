"""
圣遗物去重器
============
判断两个圣遗物是否为同一件，用于扫描时过滤重复数据。

由于原神圣遗物没有唯一 ID，同一件圣遗物可能在扫描中被重复识别。
采用短路求值策略：一旦发现任何不匹配，立即返回 False，减少耗时。
"""

from __future__ import annotations

from models.artifact import ArtifactInfo, ArtifactStat
from utils.logger import log


class ArtifactDeduplicator:
    """圣遗物去重器

    去重规则（按顺序短路求值）：
    1. 套装名不同 → 不同
    2. 部位不同 → 不同
    3. 星级不同 → 不同
    4. 主词条不同 → 不同
    5. 副词条数量不同 → 不同
    6. 副词条名称/顺序/数值不同 → 不同
    7. 以上全部匹配 → 极大概率是同一件（概率趋近于 100%）

    注意：等级不作为判断条件，因为等级变化时副词条也会随之变化，
    已由规则 5/6 隐式覆盖。
    """

    # OCR 数值浮点容差（避免微小 OCR 偏差导致误判）
    VALUE_TOLERANCE: float = 0.15

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    @staticmethod
    def is_duplicate(
        new_artifact: ArtifactInfo,
        existing_artifact: ArtifactInfo,
    ) -> bool:
        """判断两个圣遗物是否为同一件（短路求值）。

        Args:
            new_artifact: 新扫描到的圣遗物
            existing_artifact: 已有的圣遗物

        Returns:
            True 表示是重复的同一件圣遗物，False 表示不同
        """
        # 1. 套装名不同 → 不是同一件
        if new_artifact.set_name != existing_artifact.set_name:
            return False

        # 2. 部位不同 → 不是同一件
        if new_artifact.piece_type != existing_artifact.piece_type:
            return False

        # 3. 星级不同 → 不是同一件
        if new_artifact.rarity != existing_artifact.rarity:
            return False

        # 4. 主词条不同 → 不是同一件
        if not ArtifactDeduplicator._stats_equal(
            new_artifact.main_stat,
            existing_artifact.main_stat,
        ):
            return False

        # 5. 副词条数量不同 → 不是同一件
        new_subs = new_artifact.sub_stats
        existing_subs = existing_artifact.sub_stats
        if len(new_subs) != len(existing_subs):
            return False

        # 6. 副词条名称/顺序/数值逐一比较
        for ns, es in zip(new_subs, existing_subs):
            if not ArtifactDeduplicator._stats_equal(ns, es):
                return False

        # 全部匹配 → 极大概率是同一件圣遗物
        log.debug(
            f"去重: 判定为重复圣遗物 → 套装名/部位/星级/主词条/副词条全部匹配\n"
            f"  新: {ArtifactDeduplicator._format_artifact(new_artifact)}\n"
            f"  旧: {ArtifactDeduplicator._format_artifact(existing_artifact)}"
        )
        return True

    @staticmethod
    def deduplicate(artifacts: list[ArtifactInfo]) -> list[ArtifactInfo]:
        """对扫描结果列表去重，保留首次出现的圣遗物。

        使用 O(n²) 朴素比较，适用于圣遗物数量通常不超过 2000 的场景。
        若需要更高性能，可改为按套装+部位+星级分组后组内比较。

        Args:
            artifacts: 扫描结果列表

        Returns:
            去重后的列表（保持原始顺序）
        """
        unique: list[ArtifactInfo] = []
        skipped = 0
        for art in artifacts:
            if any(ArtifactDeduplicator.is_duplicate(art, u) for u in unique):
                skipped += 1
                continue
            unique.append(art)
        if skipped > 0:
            log.info(f"圣遗物去重: 跳过 {skipped} 件重复, 保留 {len(unique)} 件")
        return unique

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------

    @staticmethod
    def _format_artifact(artifact: ArtifactInfo) -> str:
        """格式化圣遗物为单行调试字符串"""
        if artifact.is_material:
            name = artifact.material_name or "强化材料"
            star = f"{artifact.rarity}★" if artifact.rarity else ""
            return f"[{star} {name}]"

        parts: list[str] = []
        if artifact.rarity:
            parts.append(f"{artifact.rarity}★")
        if artifact.set_name:
            parts.append(artifact.set_name)
        if artifact.piece_name:
            parts.append(artifact.piece_name)
        if artifact.level is not None:
            parts.append(f"+{artifact.level}")
        if artifact.main_stat:
            ms = artifact.main_stat
            pct = "%" if ms.is_percentage else ""
            parts.append(f"{ms.name}+{ms.value}{pct}")
        if artifact.sub_stats:
            subs: list[str] = []
            for ss in artifact.sub_stats:
                pct = "%" if ss.is_percentage else ""
                lock = "(待激活)" if ss.is_locked else ""
                subs.append(f"{ss.name}+{ss.value}{pct}{lock}")
            parts.append("｜".join(subs))
        return " | ".join(parts)

    @staticmethod
    def _stats_equal(a: ArtifactStat | None, b: ArtifactStat | None) -> bool:
        """比较两个词条是否相等（含浮点容差）。

        注意：is_locked 不参与比较，因为它是 OCR 解析产物而非游戏数据。
        """
        if a is None and b is None:
            return True
        if a is None or b is None:
            return False
        if a.name != b.name:
            return False
        if a.is_percentage != b.is_percentage:
            return False
        return abs(a.value - b.value) <= ArtifactDeduplicator.VALUE_TOLERANCE