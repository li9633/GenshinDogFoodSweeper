"""
圣遗物套装数据获取器
====================
从米游社百科 API 拉取圣遗物套装原始数据，解析并转换为项目统一格式的 JSON 结构，
保存到本地 data 目录。

流程: 拉取 → 解析 → 保存
"""

import json
import re
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, ClassVar

import requests
from utils.logger import log

# 米游社百科 — 圣遗物频道 API
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

# 米游社百科 — 圣遗物部位详情 API
SLOT_DETAIL_API_URL = (
    "https://act-api-takumi-static.mihoyo.com/"
    "hoyowiki/genshin/wapi/entry_page"
    "?app_sn=ys_obc&entry_page_id={entry_page_id}&lang=zh-cn"
)

# 并发配置
MAX_WORKERS = 5          # 最大并发线程数
MAX_RETRIES = 3           # 部位拉取最大重试次数
RETRY_BASE_DELAY = 0.5    # 重试基础延迟（秒），指数退避

# 圣遗物五个部位
SLOT_TYPE_NAMES: set[str] = {"生之花", "死之羽", "时之沙", "空之杯", "理之冠"}


class ArtifactSetFetcher:
    """圣遗物套装数据获取器 — 拉取、解析、保存"""

    # 星级映射
    RARITY_MAP: ClassVar[dict[str, str]] = {
        "一星": "1",
        "二星": "2",
        "三星": "3",
        "四星": "4",
        "五星": "5",
    }

    # 件套 key 到规范化 key 的正则映射
    SET_KEY_PATTERNS: ClassVar[list[tuple[str, str]]] = [
        (r"^2件套", "2pc"),
        (r"^4件套", "4pc"),
        (r"^1件套", "1pc"),
    ]

    @classmethod
    def fetch_slots_for_set(
        cls, entry_page_id: int, expected_count: int = 5
    ) -> list[dict[str, str]]:
        """
        拉取指定圣遗物套装的部位详情。

        参数:
            entry_page_id: 套装 content_id
            expected_count: 期望部位数（1件套=1，2/4件套=5）

        返回:
            部位列表，每项包含 type/name/icon/description/story
        """
        url = SLOT_DETAIL_API_URL.format(entry_page_id=entry_page_id)
        resp = requests.get(url, headers=API_HEADERS, timeout=30)
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        if data.get("retcode") != 0:
            raise ValueError(f"API retcode != 0, entry_page_id={entry_page_id}")
        # 3. 解析部位
        slots = cls._parse_slots_from_detail(data, entry_page_id)
        if len(slots) < expected_count:
            log.warning(
                f"部位不完整: entry_page_id={entry_page_id}, "
                f"期望{expected_count}个, 实际{len(slots)}个, 原始API: {url}"
            )
        return slots

    @classmethod
    def fetch_slots_for_set_with_retry(
        cls,
        entry_page_id: int,
        set_name: str,
        max_retries: int = MAX_RETRIES,
        expected_count: int = 5,
    ) -> list[dict[str, str]]:
        """带重试的拉取部位详情（指数退避），异常/空结果/数量不足都会触发重试"""
        for attempt in range(1, max_retries + 1):
            try:
                slots = cls.fetch_slots_for_set(entry_page_id, expected_count)
                if len(slots) >= expected_count:
                    return slots
                raise ValueError(f"API returned {len(slots)} slots, expected {expected_count}")
            except Exception as e:  # noqa: BLE001
                if attempt < max_retries:
                    delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                    log.warning(f"拉取失败: {set_name} (id={entry_page_id})，"
                                f"第 {attempt}/{max_retries} 次重试，等待 {delay:.1f}s — {e}")
                    time.sleep(delay)
                else:
                    log.error(f"拉取失败: {set_name} (id={entry_page_id})，"
                              f"已重试 {max_retries} 次，放弃")
        return []

    @classmethod
    def run_concurrent(
        cls,
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> list[dict[str, Any]]:
        """并发拉取所有套装部位，带进度回调"""
        raw_data = cls.fetch_from_api()
        if raw_data is None:
            log.error("拉取数据失败，流程终止")
            return []

        data = cls.parse(raw_data)
        if not data:
            log.warning("解析结果为空")
            return []

        total = len(data)
        all_slots: list[dict[str, Any]] = []
        total_expected = 0

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {}
            for item in data:
                set_id = item.get("id", 0)
                if not set_id:
                    continue
                # 根据套装效果推断期望部位数：1件套=1，2/4件套=5
                effects = item.get("setEffects", {})
                if "1pc" in effects and "2pc" not in effects and "4pc" not in effects:
                    expected = 1
                else:
                    expected = 5
                total_expected += expected
                future = executor.submit(
                    cls.fetch_slots_for_set_with_retry,
                    set_id, item["name"], MAX_RETRIES, expected,
                )
                futures[future] = item

            for i, future in enumerate(as_completed(futures), 1):
                item = futures[future]
                set_id = item.get("id", 0)
                effects = item.get("setEffects", {})
                if "1pc" in effects and "2pc" not in effects and "4pc" not in effects:
                    expected = 1
                else:
                    expected = 5
                try:
                    slots = future.result()
                    if len(slots) < expected:
                        log.error(
                            f"跳过: {item['name']} (id={set_id}) — "
                            f"期望{expected}个, 实际{len(slots)}个"
                        )
                        if progress_callback:
                            progress_callback(i, total, f"失败: {item['name']}")
                        continue
                    item["slots"] = slots
                    for slot in slots:
                        all_slots.append({
                            "setId": set_id,
                            "setName": item["name"],
                            **slot,
                        })
                    if progress_callback:
                        progress_callback(i, total, item["name"])
                except Exception:  # noqa: BLE001
                    log.error(f"跳过: {item['name']} (id={set_id})")
                    if progress_callback:
                        progress_callback(i, total, f"失败: {item['name']}")

        cls._sync_to_db(data, all_slots, total_expected)
        return data

    @classmethod
    def _parse_slots_from_detail(
        cls, raw_data: dict[str, Any], entry_page_id: int = 0
    ) -> list[dict[str, str]]:
        """
        从部位详情 API 响应中解析五个部位。

        参数:
            raw_data: API 响应 JSON

        返回:
            部位列表
        """
        modules = raw_data.get("data", {}).get("page", {}).get("modules", [])
        slots: list[dict[str, str]] = []

        for module in modules:
            components = module.get("components", [])
            if not components:
                log.debug(f"跳过空组件: id={entry_page_id}, module_name={module.get('name', '')!r}")
                continue

            try:
                comp_data = json.loads(components[0].get("data", "{}"))
            except (json.JSONDecodeError, TypeError) as e:
                comp_id = components[0].get("component_id", "?")
                log.warning(
                    f"JSON解析失败: id={entry_page_id}, "
                    f"component_id={comp_id!r}, error={e}"
                )
                continue

            # 推断部位类型：旧版 API 用 module.name，新版 API 用 data.name.key（如"生之花："）
            module_name = module.get("name", "")
            if module_name in SLOT_TYPE_NAMES:
                slot_type = module_name
            else:
                slot_type = comp_data.get("name", {}).get("key", "").rstrip("：:").strip()
                if slot_type not in SLOT_TYPE_NAMES:
                    comp_id = components[0].get("component_id", "?")
                    # 仅 artifact_list_v2 是部位数据，其他组件静默跳过
                    if comp_id == "artifact_list_v2":
                        log.debug(
                            f"跳过未知部位: id={entry_page_id}, "
                            f"module_name={module_name!r}, slot_type={slot_type!r}"
                        )
                    continue

            name_values = comp_data.get("name", {}).get("value", [])
            desc_values = comp_data.get("desc", {}).get("value", [])
            story_values = comp_data.get("story", {}).get("value", [])

            slots.append({
                "type": slot_type,
                "name": cls._strip_html(name_values[0]) if name_values else "",
                "icon": comp_data.get("icon_url", ""),
                "description": cls._strip_html(desc_values[0]) if desc_values else "",
                "story": cls._strip_html(story_values[0]) if story_values else "",
            })

        return slots

    @staticmethod
    def _strip_html(text: str) -> str:
        """去除 HTML 标签，保留纯文本。"""
        return re.sub(r"<[^>]+>", "", text).strip()

    @classmethod
    def fetch_from_api(cls) -> dict[str, Any] | None:
        """
        从米游社百科 API 拉取圣遗物原始数据。

        返回:
            API 响应的完整 JSON 数据，失败返回 None
        """
        try:
            log.info("正在从 API 拉取圣遗物数据...")
            resp = requests.get(API_URL, headers=API_HEADERS, timeout=30)
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
            if data.get("retcode") != 0:
                log.error(f"API 返回错误: retcode={data.get('retcode')}, message={data.get('message')}")
                return None
            log.info("API 数据拉取成功")
            return data
        except requests.RequestException as e:
            log.error(f"API 请求失败: {e}")
            return None

    @classmethod
    def parse_from_file(cls, file_path: str | Path) -> list[dict[str, Any]]:
        """
        从本地原始 JSON 文件解析圣遗物套装数据（用于离线/测试）。

        参数:
            file_path: 原始 API 响应 JSON 文件路径

        返回:
            解析后的圣遗物套装列表
        """
        file_path = Path(file_path)
        if not file_path.exists():
            log.error(f"文件不存在: {file_path}")
            return []

        with open(file_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        return cls.parse(raw_data)

    @classmethod
    def parse(cls, raw_data: dict[str, Any]) -> list[dict[str, Any]]:
        """
        解析原始 API 响应数据。

        参数:
            raw_data: API 响应的完整 JSON 数据

        返回:
            解析后的圣遗物套装列表
        """
        items = raw_data.get("data", {}).get("list", [])
        if not items:
            log.warning("API 响应中未找到圣遗物数据")
            return []

        artifact_list = items[0].get("list", [])
        if not artifact_list:
            log.warning("圣遗物列表为空")
            return []

        result: list[dict[str, Any]] = []
        for item in artifact_list:
            parsed = cls._parse_single_item(item)
            if parsed:
                result.append(parsed)

        log.info(f"成功解析 {len(result)} 个圣遗物套装")
        return result

    @classmethod
    def _parse_single_item(cls, item: dict[str, Any]) -> dict[str, Any] | None:
        """
        解析单个圣遗物套装条目。

        参数:
            item: 原始条目数据

        返回:
            格式化后的圣遗物套装数据，解析失败返回 None
        """
        try:
            ext_raw = item.get("ext", "{}")
            ext = json.loads(ext_raw)
            c_218 = ext.get("c_218", {})
        except (json.JSONDecodeError, TypeError):
            log.warning(f"解析 ext 字段失败: {item.get('title', '未知')}")
            return None

        # 解析 filter
        filter_data = c_218.get("filter", {})
        filter_text = filter_data.get("text", "[]")
        try:
            filter_items: list[str] = json.loads(filter_text)
        except (json.JSONDecodeError, TypeError):
            filter_items = []

        rarity, tags, sources = cls._parse_filter_items(filter_items)

        # 解析 table（套装效果）
        table_data = c_218.get("table", {})
        table_list = table_data.get("list", [])
        set_effects = cls._parse_set_effects(table_list)

        return {
            "id": item.get("content_id", 0),
            "name": item.get("title", ""),
            "icon": item.get("icon", ""),
            "summary": item.get("summary", ""),
            "rarity": rarity,
            "setEffects": set_effects,
            "tags": tags,
            "sources": sources,
        }

    @classmethod
    def _parse_filter_items(
        cls, filter_items: list[str]
    ) -> tuple[list[str], list[str], list[str]]:
        """
        从 filter 条目中分离星级、标签、获取方式。

        参数:
            filter_items: filter 文本数组，如 ["星级/五星", "套装效果/攻击力", "获取方式/秘境"]

        返回:
            (rarity, tags, sources) 三元组
        """
        rarity: list[str] = []
        tags: list[str] = []
        sources: list[str] = []

        for item in filter_items:
            if item.startswith("星级/"):
                star_name = item[len("星级/") :]
                mapped = cls.RARITY_MAP.get(star_name)
                if mapped:
                    rarity.append(mapped)
            elif item.startswith("套装效果/"):
                tag = item[len("套装效果/") :]
                if tag:
                    tags.append(tag)
            elif item.startswith("获取方式/"):
                source = item[len("获取方式/") :]
                if source:
                    sources.append(source)

        return rarity, tags, sources

    @classmethod
    def _parse_set_effects(cls, table_list: list[dict[str, str]]) -> dict[str, str]:
        """
        解析套装效果表，将 key 规范化为 2pc/4pc/1pc。

        参数:
            table_list: table.list 数组

        返回:
            如 {"2pc": "攻击力提高18%。", "4pc": "..."}
        """
        effects: dict[str, str] = {}
        for entry in table_list:
            key = entry.get("key", "")
            value = entry.get("value", "")
            normalized_key = cls._normalize_set_key(key)
            if normalized_key:
                effects[normalized_key] = value
        return effects

    @classmethod
    def _normalize_set_key(cls, key: str) -> str:
        """
        将件套 key 规范化。

        例如:
            "2件套" / "2件套：" / "2件套效果" → "2pc"
            "4件套" / "4件套：" / "4件套效果" → "4pc"

        参数:
            key: 原始 key

        返回:
            规范化后的 key，无法匹配返回空字符串
        """
        for pattern, normalized in cls.SET_KEY_PATTERNS:
            if re.match(pattern, key):
                return normalized
        return ""

    @classmethod
    def _sync_to_db(
        cls,
        sets: list[dict[str, Any]],
        all_slots: list[dict[str, Any]],
        total_expected: int = 0,
    ) -> None:
        """通过 Repository 层将套装和部位写入 artifacts.db"""
        from database.repository.artifact_piece_repo import ArtifactPieceRepo
        from database.repository.artifact_set_repo import ArtifactSetRepo

        for s in sets:
            ArtifactSetRepo.upsert(**s)

        # 按 set_id 分组，先删后插
        from collections import defaultdict

        groups: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for p in all_slots:
            groups[p["setId"]].append(p)

        for set_id, slots in groups.items():
            ArtifactPieceRepo.delete_by_set_id(set_id)
            ArtifactPieceRepo.save_batch(slots)

        # 构建同步完成日志（含达成率）
        actual = len(all_slots)
        if total_expected > 0:
            rate = actual / total_expected * 100
            log.info(
                f"同步完成: {len(sets)} 个套装, "
                f"{actual} 个部位, 期望{total_expected}个, 达成率{rate:.1f}%"
            )
        else:
            log.info(f"同步完成: {len(sets)} 个套装, {actual} 个部位")

    @classmethod
    def run(cls) -> list[dict[str, Any]]:
        """
        一键执行：拉取 → 解析 → 拉取部位 → 入库。

        返回:
            解析后的圣遗物套装列表
        """
        raw_data = cls.fetch_from_api()
        if raw_data is None:
            log.error("拉取数据失败，流程终止")
            return []

        data = cls.parse(raw_data)
        if not data:
            log.warning("解析结果为空")
            return []

        # 逐个拉取部位详情
        all_slots: list[dict[str, Any]] = []
        total_expected = 0
        for item in data:
            set_id = item.get("id", 0)
            if set_id:
                effects = item.get("setEffects", {})
                if "1pc" in effects and "2pc" not in effects and "4pc" not in effects:
                    expected = 1
                else:
                    expected = 5
                total_expected += expected
                log.info(f"拉取部位详情: {item['name']} (id={set_id})")
                slots = cls.fetch_slots_for_set(set_id, expected)
                item["slots"] = slots
                for slot in slots:
                    all_slots.append({
                        "setId": set_id,
                        "setName": item["name"],
                        **slot,
                    })

        cls._sync_to_db(data, all_slots, total_expected)
        return data


def main():
    """命令行入口：拉取 API → 解析 → 入库"""
    import sys

    sys.path.insert(0, str(Path(__file__).parent.parent))

    from utils.logger import setup_logging

    setup_logging()

    data = ArtifactSetFetcher.run()

    print(f"\n同步完成，共 {len(data)} 个圣遗物套装")


if __name__ == "__main__":
    main()