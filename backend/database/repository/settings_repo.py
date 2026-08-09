"""
应用设置 Repository
===================
键值对存储，对应 app_settings 表。
新增设置无需 ALTER TABLE，直接 INSERT 即可。
"""

from __future__ import annotations

import sqlite3

from database.connection import get_db
from utils.datetime_helper import DateTimeHelper


class SettingsRepo:
    """app_settings 表数据访问"""

    DB_NAME = "settings.db"

    # ---------- DDL ----------

    @classmethod
    def create_table(cls) -> None:
        """创建 app_settings 表（幂等）"""
        with get_db(cls.DB_NAME) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS app_settings (
                    key         TEXT PRIMARY KEY,
                    value       TEXT NOT NULL,
                    type        TEXT NOT NULL DEFAULT 'string',
                    updated_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
                )
            """)

    # ---------- 读 ----------

    @classmethod
    def get(cls, key: str, default: str | None = None) -> str | None:
        """读取单个设置值"""
        try:
            with get_db(cls.DB_NAME) as conn:
                row = conn.execute(
                    "SELECT value FROM app_settings WHERE key = ?", (key,)
                ).fetchone()
                return row["value"] if row else default
        except sqlite3.OperationalError:
            return default

    @classmethod
    def get_all(cls) -> dict[str, str]:
        """读取全部设置，返回 {key: value}"""
        try:
            with get_db(cls.DB_NAME) as conn:
                rows = conn.execute("SELECT key, value FROM app_settings").fetchall()
                return {row["key"]: row["value"] for row in rows}
        except sqlite3.OperationalError:
            return {}

    # ---------- 写 ----------

    @classmethod
    def set(cls, key: str, value: str, type_: str = "string") -> None:
        """插入或更新设置"""
        now = DateTimeHelper.now_str()
        with get_db(cls.DB_NAME) as conn:
            conn.execute(
                """
                INSERT INTO app_settings (key, value, type, updated_at)
                VALUES (:key, :value, :type, :now)
                ON CONFLICT(key) DO UPDATE SET
                    value      = excluded.value,
                    type       = excluded.type,
                    updated_at = excluded.updated_at
                """,
                {"key": key, "value": value, "type": type_, "now": now},
            )

    @classmethod
    def delete(cls, key: str) -> None:
        """删除设置（回退到默认值）"""
        with get_db(cls.DB_NAME) as conn:
            conn.execute("DELETE FROM app_settings WHERE key = ?", (key,))