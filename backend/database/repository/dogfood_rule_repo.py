"""狗粮规则 Repository
====================
在 artifacts.db 中管理 dogfood_rules 表。
"""

from __future__ import annotations

import json

from database.connection import get_db
from models.dogfood_rule import DogfoodRule


class DogfoodRuleRepo:
    """dogfood_rules 表数据访问"""

    DB_NAME = "artifacts.db"

    # ---------- DDL ----------

    @classmethod
    def create_table(cls) -> None:
        """创建 dogfood_rules 表（幂等）"""
        with get_db(cls.DB_NAME) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS dogfood_rules (
                    name         TEXT PRIMARY KEY,
                    part         TEXT NOT NULL DEFAULT '*',
                    part_exclude TEXT NOT NULL DEFAULT '',
                    main_stat    TEXT NOT NULL DEFAULT '*',
                    set_name     TEXT NOT NULL DEFAULT '*',
                    sub_stats    TEXT NOT NULL DEFAULT '[]',
                    sub_count    INTEGER NOT NULL DEFAULT 0,
                    action       TEXT NOT NULL DEFAULT 'keep',
                    priority     INTEGER NOT NULL DEFAULT 0,
                    enabled      INTEGER NOT NULL DEFAULT 1,
                    created_at   TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                    updated_at   TEXT NOT NULL DEFAULT (datetime('now','localtime'))
                )
            """)

    # ---------- 读 ----------

    @classmethod
    def find_all(cls) -> list[DogfoodRule]:
        """查询全部规则"""
        with get_db(cls.DB_NAME) as conn:
            rows = conn.execute(
                "SELECT * FROM dogfood_rules ORDER BY priority DESC, name"
            ).fetchall()
            rules: list[DogfoodRule] = []
            for row in rows:
                d = dict(row)
                d["sub_stats"] = json.loads(d.get("sub_stats", "[]"))
                d["enabled"] = bool(d.get("enabled", 1))
                rules.append(DogfoodRule.from_dict(d))
            return rules

    # ---------- 写 ----------

    @classmethod
    def upsert(cls, rule: DogfoodRule) -> None:
        """插入或更新单条规则"""
        d = rule.to_dict()
        with get_db(cls.DB_NAME) as conn:
            conn.execute(
                """
                INSERT INTO dogfood_rules
                    (name, part, part_exclude, main_stat, set_name,
                     sub_stats, sub_count, action, priority, enabled,
                     updated_at)
                VALUES
                    (:name, :part, :part_exclude, :main_stat, :set_name,
                     :sub_stats, :sub_count, :action, :priority, :enabled,
                     datetime('now','localtime'))
                ON CONFLICT(name) DO UPDATE SET
                    part         = excluded.part,
                    part_exclude = excluded.part_exclude,
                    main_stat    = excluded.main_stat,
                    set_name     = excluded.set_name,
                    sub_stats    = excluded.sub_stats,
                    sub_count    = excluded.sub_count,
                    action       = excluded.action,
                    priority     = excluded.priority,
                    enabled      = excluded.enabled,
                    updated_at   = excluded.updated_at
                """,
                {
                    "name": d["name"],
                    "part": d["part"],
                    "part_exclude": d["part_exclude"],
                    "main_stat": d["main_stat"],
                    "set_name": d["set_name"],
                    "sub_stats": json.dumps(d["sub_stats"], ensure_ascii=False),
                    "sub_count": d["sub_count"],
                    "action": d["action"],
                    "priority": d["priority"],
                    "enabled": int(d["enabled"]),
                },
            )

    @classmethod
    def exists(cls, name: str) -> bool:
        """检查规则名称是否已存在"""
        with get_db(cls.DB_NAME) as conn:
            row = conn.execute(
                "SELECT 1 FROM dogfood_rules WHERE name = ?", (name,)
            ).fetchone()
            return row is not None

    @classmethod
    def delete(cls, name: str) -> None:
        """删除单条规则"""
        with get_db(cls.DB_NAME) as conn:
            conn.execute("DELETE FROM dogfood_rules WHERE name = ?", (name,))

    @classmethod
    def save_all(cls, rules: list[DogfoodRule]) -> None:
        """全量替换（用于导入、优先级重排等场景）"""
        with get_db(cls.DB_NAME) as conn:
            conn.execute("DELETE FROM dogfood_rules")
            for rule in rules:
                d = rule.to_dict()
                conn.execute(
                    """
                    INSERT INTO dogfood_rules
                        (name, part, part_exclude, main_stat, set_name,
                         sub_stats, sub_count, action, priority, enabled)
                    VALUES
                        (:name, :part, :part_exclude, :main_stat, :set_name,
                         :sub_stats, :sub_count, :action, :priority, :enabled)
                    """,
                    {
                        "name": d["name"],
                        "part": d["part"],
                        "part_exclude": d["part_exclude"],
                        "main_stat": d["main_stat"],
                        "set_name": d["set_name"],
                        "sub_stats": json.dumps(d["sub_stats"], ensure_ascii=False),
                        "sub_count": d["sub_count"],
                        "action": d["action"],
                        "priority": d["priority"],
                        "enabled": int(d["enabled"]),
                    },
                )