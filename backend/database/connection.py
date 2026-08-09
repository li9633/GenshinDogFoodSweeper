"""
数据库连接管理
==============
提供统一的数据库连接获取接口。
每个数据库文件独立管理，使用 WAL 模式提升并发性能。
"""

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

# 数据目录: <项目根>/data/
DATA_DIR = Path(__file__).parent.parent.parent / "data"


def get_connection(db_name: str) -> sqlite3.Connection:
    """
    获取指定数据库文件的连接。

    参数:
        db_name: 数据库文件名，如 "artifacts.db"、"app.db"

    返回:
        sqlite3.Connection 实例（已开启 WAL 模式和外键约束）
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    db_path = DATA_DIR / db_name
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def get_db(db_name: str) -> Generator[sqlite3.Connection]:
    """
    数据库连接上下文管理器 — 自动 commit / rollback / close。

    用法:
        with get_db("artifacts.db") as conn:
            conn.execute("SELECT ...")
    """
    conn = get_connection(db_name)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()