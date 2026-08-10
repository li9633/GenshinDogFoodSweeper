"""
圣遗物套装实体
==============
对应 artifacts.db 中的 artifact_sets 表。
"""

import json
import sqlite3
from typing import Any


class ArtifactSet:
    """圣遗物套装实体 — 一个实体对应 artifact_sets 表"""

    __slots__ = (
        "icon",
        "id",
        "name",
        "rarity",
        "set_effects",
        "summary",
    )

    def __init__(
        self,
        id: int,
        name: str,
        icon: str = "",
        summary: str = "",
        rarity: list[str] | None = None,
        set_effects: dict[str, str] | None = None,
    ):
        self.id = id
        self.name = name
        self.icon = icon
        self.summary = summary
        self.rarity = rarity or []
        self.set_effects = set_effects or {}

    # ---------- 序列化 ----------

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "ArtifactSet":
        """从数据库行对象构造实体"""
        return cls(
            id=row["id"],
            name=row["name"],
            icon=row["icon"],
            summary=row["summary"],
            rarity=json.loads(row["rarity"]),
            set_effects=json.loads(row["set_effects"]),
        )

    def to_dict(self) -> dict[str, Any]:
        """转为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "icon": self.icon,
            "summary": self.summary,
            "rarity": self.rarity,
            "set_effects": self.set_effects,
        }