"""
圣遗物部位实体
==============
对应 artifacts.db 中的 artifact_pieces 表。
"""

import sqlite3
from typing import Any


class ArtifactPiece:
    """圣遗物部位实体 — 一个实体对应 artifact_pieces 表"""

    __slots__ = (
        "description",
        "icon",
        "id",
        "name",
        "set_id",
        "type",
    )

    def __init__(
        self,
        id: int | None = None,
        set_id: int = 0,
        type: str = "",
        name: str = "",
        icon: str = "",
        description: str = "",
    ):
        self.id = id
        self.set_id = set_id
        self.type = type
        self.name = name
        self.icon = icon
        self.description = description

    # ---------- 序列化 ----------

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "ArtifactPiece":
        """从数据库行对象构造实体"""
        return cls(
            id=row["id"],
            set_id=row["set_id"],
            type=row["type"],
            name=row["name"],
            icon=row["icon"],
            description=row["description"],
        )

    def to_dict(self) -> dict[str, Any]:
        """转为字典"""
        return {
            "id": self.id,
            "set_id": self.set_id,
            "type": self.type,
            "name": self.name,
            "icon": self.icon,
            "description": self.description,
        }