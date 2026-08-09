"""
圣遗物部位 Repository
======================
对应 artifact_pieces 表的 DDL 与 CRUD 操作。
"""

from typing import Any

from database.connection import get_db
from models.artifact_piece import ArtifactPiece
from utils.datetime_helper import DateTimeHelper


class ArtifactPieceRepo:
    """artifact_pieces 表数据访问"""

    DB_NAME = "artifacts.db"

    # ---------- DDL ----------

    @classmethod
    def create_table(cls) -> None:
        """创建 artifact_pieces 表（幂等）"""
        with get_db(cls.DB_NAME) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS artifact_pieces (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    set_id      INTEGER NOT NULL,
                    type        TEXT    NOT NULL,
                    name        TEXT    NOT NULL,
                    icon        TEXT    NOT NULL DEFAULT '',
                    description TEXT    NOT NULL DEFAULT '',
                    story       TEXT    NOT NULL DEFAULT '',
                    created_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
                    updated_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
                    FOREIGN KEY (set_id) REFERENCES artifact_sets(id) ON DELETE CASCADE
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_artifact_pieces_set_id "
                "ON artifact_pieces(set_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_artifact_pieces_type "
                "ON artifact_pieces(type)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_artifact_pieces_set_type "
                "ON artifact_pieces(set_id, type)"
            )

    # ---------- CRUD ----------

    @classmethod
    def find_by_set_id(cls, set_id: int) -> list[ArtifactPiece]:
        """查询指定套装下的全部部位"""
        with get_db(cls.DB_NAME) as conn:
            rows = conn.execute(
                "SELECT * FROM artifact_pieces WHERE set_id = ? ORDER BY id",
                (set_id,),
            ).fetchall()
            return [ArtifactPiece.from_row(r) for r in rows]

    @classmethod
    def save_batch(cls, pieces: list[dict[str, Any]]) -> None:
        """批量插入部位"""
        if not pieces:
            return
        now = DateTimeHelper.now_str()
        with get_db(cls.DB_NAME) as conn:
            conn.executemany(
                "INSERT INTO artifact_pieces "
                "(set_id, type, name, icon, description, story, created_at, updated_at) "
                "VALUES (:set_id, :type, :name, :icon, :description, :story, :now, :now)",
                [
                    {
                        "set_id": p["setId"],
                        "type": p["type"],
                        "name": p["name"],
                        "icon": p.get("icon", ""),
                        "description": p.get("description", ""),
                        "story": p.get("story", ""),
                        "now": now,
                    }
                    for p in pieces
                ],
            )

    @classmethod
    def delete_by_set_id(cls, set_id: int) -> None:
        """删除指定套装下的全部部位"""
        with get_db(cls.DB_NAME) as conn:
            conn.execute("DELETE FROM artifact_pieces WHERE set_id = ?", (set_id,))

    @classmethod
    def count(cls) -> int:
        """统计部位总数"""
        with get_db(cls.DB_NAME) as conn:
            row = conn.execute("SELECT COUNT(*) FROM artifact_pieces").fetchone()
            return row[0] if row else 0