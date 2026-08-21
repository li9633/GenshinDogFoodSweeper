"""圣遗物解析结果 DTO — 从 OCR 识别结果转换而来的结构化数据"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ArtifactStat:
    """主词条"""

    name: str
    value: float
    is_percentage: bool


@dataclass
class SubStat(ArtifactStat):
    """副词条 — 继承主词条，额外包含激活状态"""

    is_activated: bool = False


@dataclass
class ArtifactInfo:
    """圣遗物/强化材料 完整信息"""

    set_name: str | None = None
    set_id: int | None = None
    piece_type: str | None = None
    piece_name: str | None = None
    rarity: int | None = None
    main_stat: ArtifactStat | None = None
    sub_stats: list[SubStat] = field(default_factory=list)
    level: int | None = None
    is_locked: bool | None = None
    set_effects: dict[str, str] | None = None
    raw_texts: dict[str, str] = field(default_factory=dict)
    is_material: bool = False
    material_name: str | None = None
    # 扫描位置（用于调试定位：第几页-第几行-第几列）
    page: int = 0
    row: int = 0
    col: int = 0