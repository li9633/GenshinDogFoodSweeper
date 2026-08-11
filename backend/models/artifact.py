"""圣遗物解析结果 DTO — 从 OCR 识别结果转换而来的结构化数据"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ArtifactStat:
    """单个词条"""

    name: str
    value: float
    is_percentage: bool
    is_locked: bool = False


@dataclass
class ArtifactInfo:
    """圣遗物完整信息"""

    set_name: str | None = None
    set_id: int | None = None
    piece_type: str | None = None
    piece_name: str | None = None
    rarity: int | None = None
    main_stat: ArtifactStat | None = None
    sub_stats: list[ArtifactStat] = field(default_factory=list)
    level: int | None = None
    is_locked: bool | None = None
    set_effects: dict[str, str] | None = None
    raw_texts: dict[str, str] = field(default_factory=dict)