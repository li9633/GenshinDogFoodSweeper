"""
圣遗物更新检查器
==========
启动时检查原神 BBS 圣遗物套装是否有新版本更新。
仅拉取套装数量进行对比，不解析详情。
"""

from __future__ import annotations

import requests
from database.repository.artifact_set_repo import ArtifactSetRepo
from utils.logger import log

# 与 artifact_set_fetcher 共用同一 API
API_URL = (
    "https://act-api-takumi-static.mihoyo.com/"
    "common/blackboard/ys_obc/v1/home/content/list"
    "?app_sn=ys_obc&channel_id=218"
)

API_HEADERS: dict[str, str] = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Origin": "https://baike.mihoyo.com",
    "Referer": "https://baike.mihoyo.com/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/151.0.0.0 Safari/537.36"
    ),
}


class VersionChecker:
    """圣遗物更新检查器 — 对比 BBS API 套装数量与本地数据库"""

    @classmethod
    def fetch_api_set_count(cls) -> int:
        """
        从 BBS API 拉取圣遗物套装数量（仅计数，不解析详情）。

        返回:
            API 返回的套装数量，失败返回 0
        """
        try:
            resp = requests.get(API_URL, headers=API_HEADERS, timeout=30)
            resp.raise_for_status()
            data: dict = resp.json()
            if data.get("retcode") != 0:
                log.warning(f"圣遗物更新检查 API 返回错误: retcode={data.get('retcode')}")
                return 0
            items = data.get("data", {}).get("list", [])
            if not items:
                return 0
            artifact_list = items[0].get("list", [])
            return len(artifact_list)
        except requests.RequestException as e:
            log.warning(f"圣遗物更新检查 API 请求失败: {e}")
            return 0

    @classmethod
    def get_db_set_count(cls) -> int:
        """获取本地数据库中的套装数量"""
        return ArtifactSetRepo.count()

    @classmethod
    def check(cls) -> dict:
        """
        执行圣遗物更新检查。

        返回:
            {
                "api_count": int,       # API 返回的套装数量
                "db_count": int,        # 本地数据库套装数量
                "need_update": bool,    # 是否需要提示更新
                "db_empty": bool,       # 本地数据库是否为空
            }
        """
        api_count = cls.fetch_api_set_count()
        db_count = cls.get_db_set_count()

        log.info(f"圣遗物更新检查: API={api_count}, DB={db_count}")

        db_empty = db_count == 0
        need_update = api_count > 0 and api_count > db_count

        return {
            "api_count": api_count,
            "db_count": db_count,
            "need_update": need_update,
            "db_empty": db_empty,
        }