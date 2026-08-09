"""
日志 Repository
===============
app_logs 表 — 持久化存储运行日志，支持按级别/时间查询。
"""

from __future__ import annotations

import sqlite3

from database.connection import get_db
from utils.datetime_helper import DateTimeHelper


class LogRepo:
    """app_logs 表数据访问"""

    DB_NAME = "logs.db"

    @classmethod
    def create_table(cls) -> None:
        """创建 app_logs 表（幂等）"""
        with get_db(cls.DB_NAME) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS app_logs (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    level       TEXT NOT NULL,
                    message     TEXT NOT NULL,
                    module      TEXT NOT NULL DEFAULT '',
                    created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_app_logs_level "
                "ON app_logs(level)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_app_logs_created_at "
                "ON app_logs(created_at)"
            )

    @classmethod
    def insert(cls, level: str, message: str, module: str = "") -> None:
        """插入一条日志"""
        now = DateTimeHelper.now_str()
        try:
            with get_db(cls.DB_NAME) as conn:
                conn.execute(
                    "INSERT INTO app_logs (level, message, module, created_at) "
                    "VALUES (:level, :message, :module, :now)",
                    {"level": level, "message": message, "module": module, "now": now},
                )
        except sqlite3.OperationalError:
            pass  # 表未创建时静默跳过

    @classmethod
    def query(
        cls, limit: int = 100, level: str | None = None
    ) -> list[dict[str, str]]:
        """查询最近日志"""
        try:
            with get_db(cls.DB_NAME) as conn:
                if level:
                    rows = conn.execute(
                        "SELECT level, message, module, created_at "
                        "FROM app_logs WHERE level = ? "
                        "ORDER BY id DESC LIMIT ?",
                        (level, limit),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT level, message, module, created_at "
                        "FROM app_logs ORDER BY id DESC LIMIT ?",
                        (limit,),
                    ).fetchall()
                return [dict(row) for row in rows]
        except sqlite3.OperationalError:
            return []