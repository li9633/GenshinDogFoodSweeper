"""
圣遗物套装 Repository
======================
对应 artifact_sets 表的 DDL 与 CRUD 操作。
"""

import json
from typing import Any

from database.connection import get_db
from models.artifact_set import ArtifactSet


class ArtifactSetRepo:
    """artifact_sets 表数据访问"""

    DB_NAME = "artifacts.db"

    # ---------- DDL ----------

    @classmethod
    def create_table(cls) -> None:
        """创建 artifact_sets 表（幂等）"""
        with get_db(cls.DB_NAME) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS artifact_sets (
                    id          INTEGER PRIMARY KEY,
                    name        TEXT    NOT NULL,
                    icon        TEXT    NOT NULL DEFAULT '',
                    summary     TEXT    NOT NULL DEFAULT '',
                    rarity      TEXT    NOT NULL DEFAULT '[]',
                    set_effects TEXT    NOT NULL DEFAULT '{}'
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_artifact_sets_name "
                "ON artifact_sets(name)"
            )

    # ---------- CRUD ----------

    @classmethod
    def find_all(cls) -> list[ArtifactSet]:
        """查询全部套装"""
        with get_db(cls.DB_NAME) as conn:
            rows = conn.execute(
                "SELECT * FROM artifact_sets ORDER BY id DESC"
            ).fetchall()
            return [ArtifactSet.from_row(r) for r in rows]

    @classmethod
    def find_by_id(cls, set_id: int) -> ArtifactSet | None:
        """按 ID 查询套装"""
        with get_db(cls.DB_NAME) as conn:
            row = conn.execute(
                "SELECT * FROM artifact_sets WHERE id = ?", (set_id,)
            ).fetchone()
            return ArtifactSet.from_row(row) if row else None

    @classmethod
    def upsert(cls, **kwargs: Any) -> None:
        """插入或更新套装（存在则更新，不存在则插入）"""
        with get_db(cls.DB_NAME) as conn:
            conn.execute(
                """
                INSERT INTO artifact_sets
                    (id, name, icon, summary, rarity, set_effects)
                VALUES
                    (:id, :name, :icon, :summary, :rarity, :set_effects)
                ON CONFLICT(id) DO UPDATE SET
                    name        = excluded.name,
                    icon        = excluded.icon,
                    summary     = excluded.summary,
                    rarity      = excluded.rarity,
                    set_effects = excluded.set_effects
                """,
                {
                    "id": kwargs["id"],
                    "name": kwargs["name"],
                    "icon": kwargs.get("icon", ""),
                    "summary": kwargs.get("summary", ""),
                    "rarity": json.dumps(kwargs.get("rarity", []), ensure_ascii=False),
                    "set_effects": json.dumps(
                        kwargs.get("set_effects", kwargs.get("setEffects", {})),
                        ensure_ascii=False,
                    ),
                },
            )

    @classmethod
    def count(cls) -> int:
        """统计套装总数"""
        with get_db(cls.DB_NAME) as conn:
            row = conn.execute("SELECT COUNT(*) FROM artifact_sets").fetchone()
            return row[0] if row else 0

    @classmethod
    def delete_all(cls) -> int:
        """清空所有套装记录，返回删除行数"""
        with get_db(cls.DB_NAME) as conn:
            count = conn.execute("SELECT COUNT(*) FROM artifact_sets").fetchone()[0]
            conn.execute("DELETE FROM artifact_sets")
            return count