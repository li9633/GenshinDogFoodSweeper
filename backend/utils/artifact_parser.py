"""圣遗物 OCR 文本解析器 — 将识别结果转换为结构化数据"""

from __future__ import annotations

import json
import re
from typing import ClassVar

from models.artifact import ArtifactInfo, ArtifactStat, SubStat
from utils.logger import log

from backend.models.artifact_recognition_field import ArtifactRecognitionField
from common.resources import Resource

# ========== 加载词条模板 ==========

_STATS_JSON = Resource.ARTIFACT_STATS_JSON
with open(_STATS_JSON, encoding="utf-8") as _f:
    _TEMPLATE: dict = json.load(_f)

_STATS: dict[str, dict] = _TEMPLATE["stats"]
_MAIN_STATS_BY_PIECE: dict[str, list[str]] = _TEMPLATE["main_stats_by_piece"]
_SUB_STAT_NAMES: list[str] = _TEMPLATE["sub_stat_names"]
_RULES: dict = _TEMPLATE["rules"]

# 全部词条名并集（用于模糊匹配）
_ALL_STAT_NAMES: set[str] = set(_STATS.keys())
# 不需要 % 就能确定是百分比类型的词条名
_ALWAYS_PCT: frozenset[str] = frozenset(
    k for k, v in _STATS.items() if v["always_pct"]
)


# ========== 解析器 ==========


class ArtifactTextParser:
    """圣遗物 OCR 文本 → 结构化数据"""

    SUB_SPLIT_RE: ClassVar[re.Pattern] = re.compile(r"\s*[|·•。]\s*")
    MAIN_SPLIT_RE: ClassVar[re.Pattern] = re.compile(r"\s*\|\s*")
    LOCKED_RE: ClassVar[re.Pattern] = re.compile(
        r"[（(]\s*(待激活|未激活|激活)\s*[）)]|待激活|未激活"
    )
    LEADING_SYMBOL_RE: ClassVar[re.Pattern] = re.compile(r"^[•·。.,,，、\-\s]+")
    STAT_PLUS_RE: ClassVar[re.Pattern] = re.compile(
        r"^(.+?)\s*[＋+]\s*([\d,]+\.?\d*\s*%?)$"
    )
    STAT_SPACE_RE: ClassVar[re.Pattern] = re.compile(r"^(.+?)\s+([\d,]+\.?\d*\s*%?)$")

    @classmethod
    def parse(
        cls,
        set_name: str | None,
        piece_type: str | None,
        piece_name: str | None,
        name_ocr: str,
        main_ocr: str,
        sub_ocr: str,
        level_ocr: str = "",
        lock_ocr: str = "",
        set_id: int | None = None,
        fields: frozenset[ArtifactRecognitionField] | None = None,
    ) -> ArtifactInfo:
        """从 OCR 文本解析圣遗物信息。

        Args:
            fields: 识别策略，None 则全部解析
        """
        is_all = fields is None or ArtifactRecognitionField.ALL in fields
        need_main = is_all or ArtifactRecognitionField.MAIN_STAT in fields
        need_sub = is_all or ArtifactRecognitionField.SUB_STATS in fields
        need_level = is_all or ArtifactRecognitionField.LEVEL in fields
        need_lock = is_all or ArtifactRecognitionField.LOCK_STATUS in fields
        need_effects = is_all or ArtifactRecognitionField.SET_EFFECTS in fields

        info = ArtifactInfo(
            set_name=set_name,
            piece_type=piece_type,
            piece_name=piece_name,
            raw_texts={
                "圣遗物名称": name_ocr,
                "部位+主词条": main_ocr,
                "副词条区": sub_ocr,
                "圣遗物等级": level_ocr,
                "圣遗物锁定状态": lock_ocr,
            },
        )
        if need_effects and set_id is not None:
            info.set_effects = cls._lookup_set_effects(set_id)
        if need_main and piece_type and main_ocr:
            info.main_stat = cls._parse_main_stat(main_ocr, piece_type)
        if need_sub and sub_ocr:
            info.sub_stats = cls._parse_sub_stats(sub_ocr)
        if need_level and level_ocr:
            info.level = cls._parse_level(level_ocr)
        if need_lock and lock_ocr:
            info.is_locked = cls._parse_lock_status(lock_ocr)
        # 规则校验
        info = cls._validate(info)
        return info

    # ---------- 等级 & 锁定状态 ----------

    @staticmethod
    def _parse_level(text: str) -> int | None:
        """解析等级文本：'+20' → 20"""
        m = re.search(r"[＋+]\s*(\d+)", text)
        if m:
            return int(m.group(1))
        return None

    @staticmethod
    def _parse_lock_status(text: str) -> bool | None:
        """解析锁定状态：'锁定'/'已锁' 等 → True，'未锁'/'解锁' 等 → False"""
        locked_kw = ["锁定", "已锁", "上锁", "🔒"]
        unlocked_kw = ["未锁", "解锁", "开锁", "🔓"]
        for kw in locked_kw:
            if kw in text:
                return True
        for kw in unlocked_kw:
            if kw in text:
                return False
        return None

    # ---------- 校验 ----------

    @classmethod
    def _validate(cls, info: ArtifactInfo) -> ArtifactInfo:
        """对解析结果应用游戏规则校验"""
        if not _RULES.get("main_sub_no_conflict"):
            return info
        if not info.main_stat:
            return info

        main_cat = _STATS.get(info.main_stat.name, {}).get("category", "")
        if not main_cat:
            return info

        # 主词条与副词条不能同类型
        valid_subs = []
        for ss in info.sub_stats:
            sub_cat = _STATS.get(ss.name, {}).get("category", "")
            if sub_cat == main_cat:
                continue  # 冲突，剔除
            valid_subs.append(ss)
        info.sub_stats = valid_subs

        # 副词条去重（同类型只保留一个，优先保留非 locked 的）
        if _RULES.get("sub_no_duplicate"):
            seen: dict[str, SubStat] = {}
            for ss in info.sub_stats:
                sub_cat = _STATS.get(ss.name, {}).get("category", ss.name)
                if sub_cat not in seen or (not ss.is_activated and seen[sub_cat].is_activated):
                    seen[sub_cat] = ss
            info.sub_stats = list(seen.values())

        return info

    # ---------- 套装效果 ----------

    @staticmethod
    def _lookup_set_effects(set_id: int) -> dict[str, str] | None:
        """按 set_id 查询套装效果，返回 {'2pc': '...', '4pc': '...'} 或 None"""
        try:
            from database.repository.artifact_set_repo import ArtifactSetRepo

            set_obj = ArtifactSetRepo.find_by_id(set_id)
            if set_obj is None:
                log.warning(f"[套装效果] set_id={set_id} 未找到套装")
                return None
            if not set_obj.set_effects:
                log.warning(f"[套装效果] {set_obj.name} (id={set_id}) 无套装效果数据")
                return None
            log.info(f"[套装效果] {set_obj.name} (id={set_id}) → {set_obj.set_effects}")
            return set_obj.set_effects
        except Exception:
            log.warning(f"[套装效果] set_id={set_id} 查询失败")
            return None

    # ---------- 主词条 ----------

    @classmethod
    def _parse_main_stat(cls, text: str, piece_type: str) -> ArtifactStat | None:
        parts = [p.strip() for p in cls.MAIN_SPLIT_RE.split(text) if p.strip()]
        if len(parts) < 2:
            return None
        for i in range(len(parts) - 1):
            name = parts[i]
            value_str = parts[i + 1]
            if name in _ALL_STAT_NAMES or cls._fuzzy_match(name):
                return cls._build_stat(name, value_str)
        return None

    # ---------- 副词条 ----------

    @classmethod
    def _parse_sub_stats(cls, text: str) -> list[SubStat]:
        parts = cls.SUB_SPLIT_RE.split(text)
        results: list[SubStat] = []
        for part in parts:
            part = part.strip()
            if not part:
                continue
            cleaned = cls.LEADING_SYMBOL_RE.sub("", part)
            is_activated = not bool(cls.LOCKED_RE.search(cleaned))
            cleaned = cls.LOCKED_RE.sub("", cleaned).strip()
            stat = cls._split_stat_value(cleaned, is_activated)
            if stat:
                results.append(stat)
        return results

    @classmethod
    def _split_multi_stats(
        cls, text: str, is_activated: bool
    ) -> list[SubStat]:
        """兜底：处理未被 SUB_SPLIT_RE 覆盖的粘连情况"""
        inner = re.split(r"\s*[·•。]\s*", text)
        results: list[SubStat] = []
        for p in inner:
            p = cls.LEADING_SYMBOL_RE.sub("", p.strip())
            if not p:
                continue
            locked = is_activated or bool(cls.LOCKED_RE.search(p))
            p = cls.LOCKED_RE.sub("", p).strip()
            stat = cls._split_stat_value(p, locked)
            if stat:
                results.append(stat)
        return results

    @classmethod
    def _split_stat_value(cls, text: str, is_activated: bool) -> SubStat | None:
        # 尝试 + 号分割
        m = cls.STAT_PLUS_RE.match(text)
        if m:
            return cls._build_stat(m.group(1).strip(), m.group(2).strip(), is_activated)
        # 回退：空格分割（OCR 可能漏掉 + 号）
        m = cls.STAT_SPACE_RE.match(text)
        if m:
            return cls._build_stat(m.group(1).strip(), m.group(2).strip(), is_activated)
        return None

    # ---------- 工具 ----------

    @classmethod
    def _build_stat(
        cls, name: str, value_str: str, is_activated: bool | None = None
    ) -> ArtifactStat | SubStat | None:
        is_pct = "%" in value_str
        clean = value_str.replace("%", "").replace(",", "").strip()
        try:
            value = float(clean)
        except ValueError:
            return None
        # 根据数值格式匹配正确的词条名（数值型 vs 百分比型）
        matched = cls._fuzzy_match(name, is_pct)
        if not matched:
            return None
        if is_activated is not None:
            return SubStat(
                name=matched, value=value, is_percentage=is_pct, is_activated=is_activated
            )
        return ArtifactStat(
            name=matched, value=value, is_percentage=is_pct
        )

    @staticmethod
    def _fuzzy_match(text: str, is_pct: bool | None = None) -> str | None:
        from rapidfuzz import fuzz, process

        candidates = list(_ALL_STAT_NAMES)
        # 优先按数值格式筛选候选
        if is_pct is True:
            pct_candidates = [
                s for s in candidates
                if s.endswith("%") or s in _ALWAYS_PCT
            ]
            if pct_candidates:
                candidates = pct_candidates
        elif is_pct is False:
            flat_candidates = [
                s for s in candidates
                if not s.endswith("%") and s not in _ALWAYS_PCT
            ]
            if flat_candidates:
                candidates = flat_candidates
        result = process.extractOne(text, candidates, scorer=fuzz.ratio)
        return result[0] if result and result[1] >= 70 else None