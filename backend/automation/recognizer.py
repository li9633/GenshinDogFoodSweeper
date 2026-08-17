"""圣遗物识别器 — OCR 文本提取 + BBS 数据匹配 + 星级/锁定检测"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import ClassVar

import cv2
import numpy as np
from utils.logger import log

from backend.automation.color_sampler import sample_roi_color
from backend.automation.template_manager import TemplateManager
from backend.automation.template_matcher import multi_scale_match
from backend.models.artifact import ArtifactInfo
from backend.models.artifact_recognition_field import ArtifactRecognitionField
from backend.models.template import Template


class ArtifactRecognizer:
    """圣遗物识别：OCR 解析 + 套装/部位匹配 + 星级颜色分类 + 锁定状态检测"""

    PIECE_TYPES: ClassVar[set[str]] = {"生之花", "死之羽", "时之沙", "空之杯", "理之冠"}

    STRATEGY: ClassVar[frozenset[ArtifactRecognitionField]] = frozenset(
        {ArtifactRecognitionField.ALL}
    )

    RARITY_COLORS: ClassVar[tuple[tuple[int, int, int], ...]] = (
        (113, 118, 138),  # 1★ #71768A
        (42, 143, 114),  # 2★ #2A8F72
        (81, 127, 203),  # 3★ #517FCB
        (161, 86, 224),  # 4★ #A156E0
        (188, 105, 50),  # 5★ #BC6932
    )

    # ---------- 数据库工具 ----------

    @staticmethod
    def is_db_empty() -> bool:
        """检查本地圣遗物数据库是否为空"""
        try:
            from database.repository.artifact_set_repo import ArtifactSetRepo

            return ArtifactSetRepo.count() == 0
        except Exception:
            return True

    # ---------- 星级分类 ----------

    @classmethod
    def classify_rarity(cls, rgb: tuple[int, int, int]) -> int | None:
        """根据实测背景色用 RGB 欧氏距离判定星级（1~5），距离过远返回 None"""
        best_star = None
        best_dist = float("inf")
        for i, ref in enumerate(cls.RARITY_COLORS):
            dist = sum((a - b) ** 2 for a, b in zip(rgb, ref)) ** 0.5
            if dist < best_dist:
                best_dist = dist
                best_star = i + 1
        return best_star if best_dist < 80 else None

    @classmethod
    def detect_rarity_from_image(
        cls, image: np.ndarray, x: int, y: int, w: int, h: int
    ) -> int | None:
        """从截图中指定 ROI 区域采样颜色并判定星级"""
        rgb = sample_roi_color(image, x, y, w, h)
        return cls.classify_rarity(rgb)

    # ---------- BBS 套装匹配 ----------

    @staticmethod
    def match_set_name(
        text: str,
    ) -> tuple[str, int, str | None, str | None, float] | None:
        """用 OCR 文本匹配圣遗物套装。

        优先匹配 artifact_pieces.name（部位单件名），再通过 set_id 反查套装名；
        若失败则回退到直接匹配 artifact_sets.name。

        返回 (套装名, set_id, 部位类型, 部位名称, 置信度) 或 None。
        若通过单件名匹配，部位类型和名称不为 None，后续可跳过部位匹配。
        """
        try:
            from database.repository.artifact_piece_repo import ArtifactPieceRepo
            from database.repository.artifact_set_repo import ArtifactSetRepo
            from rapidfuzz import fuzz, process

            pieces = ArtifactPieceRepo.find_all_names()
            if pieces:
                piece_names = [p["name"] for p in pieces]
                result = process.extractOne(text, piece_names, scorer=fuzz.ratio)
                if result and result[1] >= 70:
                    matched_piece = next(p for p in pieces if p["name"] == result[0])
                    set_obj = ArtifactSetRepo.find_by_id(matched_piece["set_id"])
                    if set_obj:
                        return (
                            set_obj.name,
                            matched_piece["set_id"],
                            matched_piece["type"],
                            matched_piece["name"],
                            result[1] / 100.0,
                        )

            sets = ArtifactSetRepo.find_all()
            names = [s.name for s in sets]
            if names:
                result = process.extractOne(text, names, scorer=fuzz.ratio)
                if result and result[1] >= 70:
                    set_obj = next(s for s in sets if s.name == result[0])
                    return result[0], set_obj.id, None, None, result[1] / 100.0
        except Exception:
            return None

    @classmethod
    def match_piece_type(
        cls, text: str, set_id: int | None = None
    ) -> dict[str, str] | None:
        """在 OCR 文本中检测圣遗物部位，返回 {type, name} 或 None。

        优先匹配 artifact_pieces.name（单件名），其次匹配 artifact_pieces.type（部位类型）。
        若提供 set_id，则限定在指定套装内匹配，避免跨套装误匹配。
        """
        try:
            from database.repository.artifact_piece_repo import ArtifactPieceRepo
            from rapidfuzz import fuzz, process

            all_pieces = ArtifactPieceRepo.find_all_names()
            if not all_pieces:
                for pt in cls.PIECE_TYPES:
                    if pt in text:
                        return {"type": pt, "name": ""}
                return None

            pieces = (
                [p for p in all_pieces if p["set_id"] == set_id]
                if set_id is not None
                else all_pieces
            )
            if not pieces:
                pieces = all_pieces

            piece_names = [p["name"] for p in pieces]
            log.debug(
                f"[匹配部位] OCR='{text}' set_id={set_id} "
                f"候选({len(pieces)}个): {piece_names[:5]}{'...' if len(piece_names) > 5 else ''}"
            )
            result = process.extractOne(text, piece_names, scorer=fuzz.partial_ratio)
            if result:
                log.debug(f"[匹配部位] 最佳匹配: '{result[0]}' score={result[1]}")
            if result and result[1] >= 75:
                matched = next(p for p in pieces if p["name"] == result[0])
                return {"type": matched["type"], "name": matched["name"]}

            piece_types = list({(p["type"], p["name"]) for p in pieces})
            for pt, pn in piece_types:
                if pt in text:
                    return {"type": pt, "name": pn}
        except Exception:
            return None

    # ---------- 锁定状态 ----------

    @staticmethod
    def match_lock_status(
        full_image: np.ndarray,
        search_region: tuple[int, int, int, int] | None = None,
    ) -> bool | None:
        """通过模板匹配判断圣遗物锁定状态。

        搜索区域默认从 TemplateManager 获取（templates.json），
        search_region 参数仅用于覆盖（如分解页面弹窗位置不同）。

        Args:
            full_image: RGB 截图
            search_region: 搜索区域覆盖 (x, y, w, h)，None 则使用模板默认区域

        Returns:
            True=已锁, False=未锁, None=无法判断
        """
        locked = TemplateManager.get("圣遗物状态已锁定")
        unlocked = TemplateManager.get("圣遗物状态已解锁")
        if locked is None or unlocked is None:
            return None

        locked_region = search_region if search_region is not None else locked.region
        unlocked_region = search_region if search_region is not None else unlocked.region

        full_gray = cv2.cvtColor(full_image, cv2.COLOR_RGB2GRAY)

        def _match(
            template: Template, region: tuple[int, int, int, int] | None
        ) -> float:
            if region:
                rx, ry, rw, rh = region
                search_area = full_gray[ry : ry + rh, rx : rx + rw]
                if search_area.size == 0:
                    return -1.0
            else:
                search_area = full_gray
            best, _, _, _ = multi_scale_match(search_area, template)
            return best

        locked_score = _match(locked, locked_region)
        unlocked_score = _match(unlocked, unlocked_region)

        if locked_score < 0 and unlocked_score < 0:
            return None
        if locked_score > unlocked_score and locked_score > 0.8:
            return True
        if unlocked_score > locked_score and unlocked_score > 0.8:
            return False
        return None

    @staticmethod
    def find_lock_icon_position(
        full_image: np.ndarray,
        search_region: tuple[int, int, int, int] | None = None,
    ) -> tuple[int, int] | None:
        """通过模板匹配找到锁定图标在 detail 弹窗中的位置。

        优先匹配「解锁」状态（大部分圣遗物都是解锁的），
        失败后再匹配「锁定」状态，任一命中即返回。

        搜索区域默认从 TemplateManager 获取（已在 templates.json 中定义），
        search_region 参数仅用于覆盖（如分解页面弹窗位置不同）。

        Args:
            full_image: RGB 截图
            search_region: 搜索区域覆盖 (x, y, w, h)，None 则使用模板默认区域

        Returns:
            (x, y) 匹配区域的左上角绝对坐标，未找到返回 None
        """
        full_gray = cv2.cvtColor(full_image, cv2.COLOR_RGB2GRAY)

        # 优先匹配解锁（大部分圣遗物），失败再匹配锁定
        for key in ("圣遗物状态已解锁", "圣遗物状态已锁定"):
            template = TemplateManager.get(key)
            if template is None:
                continue

            region = search_region if search_region is not None else template.region
            if region is None:
                continue
            rx, ry, rw, rh = region
            if rx < 0 or ry < 0 or rx + rw > full_gray.shape[1] or ry + rh > full_gray.shape[0]:
                continue

            search_area = full_gray[ry : ry + rh, rx : rx + rw]
            score, loc, _scale, (_tw, _th) = multi_scale_match(search_area, template)
            if score >= 0.8:
                x = rx + loc[0]
                y = ry + loc[1]
                return (x, y)

        return None

    # ---------- 完整识别流水线 ----------

    @staticmethod
    def recognize(
        image: np.ndarray,
        roi_configs: dict[str, tuple[int, int, int, int]],
        ocr,
        fields: frozenset[ArtifactRecognitionField] | None = None,
        *,
        lock_anchor_search_region: tuple[int, int, int, int] | None = None,
        lock_anchor_to_level: tuple[int, int, int, int] | None = None,
        lock_anchor_to_sub_stats: tuple[int, int, int, int] | None = None,
    ) -> ArtifactInfo:
        """执行完整圣遗物识别流程：OCR → 匹配 → 解析 → 返回 ArtifactInfo

        Args:
            image: 截图 RGB 图像
            roi_configs: {区域名: (x, y, w, h), ...}
            ocr: PaddleOCR 实例
            fields: 识别策略，None 则使用类变量 STRATEGY

        Returns:
            ArtifactInfo: 包含所有识别结果的结构化对象
        """
        import time

        from utils.artifact_parser import ArtifactTextParser

        from backend.automation.color_sampler import sample_roi_color

        t0 = time.perf_counter()

        if fields is None:
            fields = ArtifactRecognizer.STRATEGY
        is_all = ArtifactRecognitionField.ALL in fields

        need_set_name = is_all or ArtifactRecognitionField.SET_NAME in fields
        need_piece_type = is_all or ArtifactRecognitionField.PIECE_TYPE in fields
        need_main_stat = is_all or ArtifactRecognitionField.MAIN_STAT in fields
        need_piece_or_main = need_piece_type or need_main_stat
        need_sub_stats = is_all or ArtifactRecognitionField.SUB_STATS in fields
        need_level = is_all or ArtifactRecognitionField.LEVEL in fields
        need_rarity = is_all or ArtifactRecognitionField.RARITY in fields
        need_lock = is_all or ArtifactRecognitionField.LOCK_STATUS in fields

        # 锁定图标锚点定位：通过模板匹配找到锁定图标，动态计算等级/副词条 ROI
        # 用于兼容自定义圣遗物等 flex 布局导致的区域偏移
        # 优先匹配解锁（大部分圣遗物），失败再匹配锁定
        if lock_anchor_to_level is not None or lock_anchor_to_sub_stats is not None:
            lock_pos = ArtifactRecognizer.find_lock_icon_position(
                image, lock_anchor_search_region
            )
            if lock_pos is not None:
                lx, ly = lock_pos
                if lock_anchor_to_level is not None:
                    dx, dy, dw, dh = lock_anchor_to_level
                    roi_configs["圣遗物等级"] = (lx + dx, ly + dy, dw, dh)
                if lock_anchor_to_sub_stats is not None:
                    dx, dy, dw, dh = lock_anchor_to_sub_stats
                    lvl_x, lvl_y = roi_configs["圣遗物等级"][:2]
                    roi_configs["副词条区"] = (lvl_x + dx, lvl_y + dy, dw, dh)

        ocr_texts: dict[str, list[str]] = {}
        matched_set_name: str | None = None
        matched_set_id: int | None = None
        matched_piece_type: str | None = None
        matched_piece_name: str | None = None
        matched_rarity: int | None = None
        matched_set_rarities: list[str] = []
        piece_from_set_match = False

        db_empty = ArtifactRecognizer.is_db_empty()

        # 根据策略过滤需要 OCR 的 ROI
        _ocr_required = {"圣遗物名称": need_set_name}
        if need_piece_or_main:
            _ocr_required["部位+主词条"] = True
        if need_sub_stats:
            _ocr_required["副词条区"] = True
        if need_level:
            _ocr_required["圣遗物等级"] = True

        # 收集所有需要 OCR 的 ROI，准备批量处理
        t_roi_collect = time.perf_counter()
        ocr_rois: list[tuple[str, np.ndarray]] = []
        for name, (x, y, w, h) in roi_configs.items():
            if not _ocr_required.get(name, False):
                continue
            roi = image[y : y + h, x : x + w]
            if roi.size == 0:
                continue
            ocr_rois.append((name, roi))
        log.debug(
            f"[耗时] ROI收集: {(time.perf_counter() - t_roi_collect) * 1000:.1f}ms "
            f"(共{len(ocr_rois)}个ROI)"
        )

        # Batch OCR：纵向拼接所有 ROI 为一张图，单次 OCR 调用
        if ocr_rois:
            t_composite = time.perf_counter()
            max_w = max(r.shape[1] for _, r in ocr_rois)
            roi_parts: list[np.ndarray] = []
            roi_y_ranges: list[tuple[str, int, int]] = []
            y_cur = 0
            for name, roi in ocr_rois:
                h, w = roi.shape[:2]
                if w < max_w:
                    pad = np.zeros((h, max_w - w, 3), dtype=np.uint8)
                    roi = np.hstack([roi, pad])
                roi_parts.append(roi)
                roi_y_ranges.append((name, y_cur, y_cur + h))
                y_cur += h

            composite = np.vstack(roi_parts)
            log.debug(
                f"[耗时] 图像拼接: {(time.perf_counter() - t_composite) * 1000:.1f}ms "
                f"(尺寸{composite.shape[1]}x{composite.shape[0]})"
            )

            ArtifactRecognizer.save_roi_temp(composite, "batch")

            t_ocr = time.perf_counter()
            ocr_result = ocr.ocr(composite)
            log.debug(
                f"[耗时] OCR推理: {(time.perf_counter() - t_ocr) * 1000:.1f}ms"
            )

            # 按 Y 坐标拆分 OCR 结果到各 ROI
            t_split = time.perf_counter()
            for name, y_start, y_end in roi_y_ranges:
                texts = ArtifactRecognizer._extract_roi_texts(
                    ocr_result, y_start, y_end
                )
                ocr_texts[name] = texts
            log.debug(
                f"[耗时] 文本拆分: {(time.perf_counter() - t_split) * 1000:.1f}ms"
            )

        # 模糊匹配（与 OCR 解耦，逻辑不变）
        if not db_empty:
            t_set_match = time.perf_counter()
            name_texts = ocr_texts.get("圣遗物名称", [])
            if name_texts:
                match = ArtifactRecognizer.match_set_name(name_texts[0])
                if match:
                    matched_set_name = match[0]
                    matched_set_id = match[1]
                    matched_piece_type = match[2]
                    matched_piece_name = match[3]
                    piece_from_set_match = match[2] is not None
                    log.debug(
                        f"[耗时] 套装匹配: {(time.perf_counter() - t_set_match) * 1000:.1f}ms "
                        f"OCR='{name_texts[0]}' → "
                        f"set_name='{match[0]}' set_id={match[1]} "
                        f"piece_type={match[2]} piece_name={match[3]} "
                        f"score={match[4]:.3f}"
                    )
                else:
                    log.debug(
                        f"[耗时] 套装匹配: {(time.perf_counter() - t_set_match) * 1000:.1f}ms "
                        f"(未匹配)"
                    )

            t_piece_match = time.perf_counter()
            main_texts_temp = ocr_texts.get("部位+主词条", [])
            if main_texts_temp and not piece_from_set_match:
                for t in main_texts_temp:
                    piece = ArtifactRecognizer.match_piece_type(
                        t, set_id=matched_set_id
                    )
                    if piece:
                        matched_piece_type = piece["type"]
                        matched_piece_name = piece["name"]
                        break
            log.debug(
                f"[耗时] 部位匹配: {(time.perf_counter() - t_piece_match) * 1000:.1f}ms"
            )

        # 星级识别
        t_rarity = time.perf_counter()
        if need_rarity and not db_empty and matched_set_id is not None:
            from database.repository.artifact_set_repo import ArtifactSetRepo

            set_obj = ArtifactSetRepo.find_by_id(matched_set_id)
            if set_obj:
                matched_set_rarities = set_obj.rarity
        if need_rarity and "圣遗物星级" in roi_configs:
            sx, sy, sw, sh = roi_configs["圣遗物星级"]
            star_roi = image[sy : sy + sh, sx : sx + sw]
            if star_roi.size > 0:
                rgb = sample_roi_color(image, sx, sy, sw, sh)
                detected = ArtifactRecognizer.classify_rarity(rgb)
                if detected is not None:
                    if matched_set_rarities:
                        if str(detected) in matched_set_rarities:
                            matched_rarity = detected
                    else:
                        matched_rarity = detected
        log.debug(
            f"[耗时] 星级识别: {(time.perf_counter() - t_rarity) * 1000:.1f}ms "
            f"(结果={matched_rarity})"
        )

        # 锁定状态（模板匹配，搜索区域默认从 TemplateManager 获取）
        t_lock = time.perf_counter()
        lock_status = None
        if need_lock:
            lock_status = ArtifactRecognizer.match_lock_status(
                image, lock_anchor_search_region
            )
        log.debug(
            f"[耗时] 锁定检测: {(time.perf_counter() - t_lock) * 1000:.1f}ms "
            f"(结果={lock_status})"
        )

        # 强化材料检测：部位区域识别到材料关键字则提前返回
        t_material = time.perf_counter()
        material_keywords = ["圣遗物强化素材", "圣遗物强化材料", "强化素材", "强化材料"]
        main_texts = ocr_texts.get("部位+主词条", [])
        for mt in main_texts:
            for kw in material_keywords:
                if kw in mt:
                    elapsed = (time.perf_counter() - t0) * 1000
                    log.info(
                        f"[识别完成] 检测到强化材料 '{mt}' → 跳过圣遗物解析 "
                        f"(耗时 {elapsed:.0f}ms)"
                    )
                    return ArtifactInfo(
                        is_material=True,
                        material_name=mt,
                        rarity=matched_rarity,
                        raw_texts={
                            "部位+主词条": " | ".join(main_texts),
                        },
                    )
        log.debug(
            f"[耗时] 材料检测: {(time.perf_counter() - t_material) * 1000:.1f}ms"
        )

        # 结构化解析
        t_parse = time.perf_counter()
        name_ocr = " | ".join(ocr_texts.get("圣遗物名称", []))
        main_ocr = " | ".join(main_texts)
        sub_ocr = " | ".join(ocr_texts.get("副词条区", []))
        level_ocr = " | ".join(ocr_texts.get("圣遗物等级", []))
        lock_ocr = (
            "锁定" if lock_status is True else ("解锁" if lock_status is False else "")
        )

        artifact = ArtifactTextParser.parse(
            set_name=matched_set_name,
            piece_type=matched_piece_type,
            piece_name=matched_piece_name,
            name_ocr=name_ocr,
            main_ocr=main_ocr,
            sub_ocr=sub_ocr,
            level_ocr=level_ocr,
            lock_ocr=lock_ocr,
            set_id=matched_set_id,
            fields=fields,
        )

        artifact.rarity = matched_rarity
        artifact.set_id = matched_set_id
        log.debug(
            f"[耗时] 结构化解析: {(time.perf_counter() - t_parse) * 1000:.1f}ms"
        )

        elapsed = (time.perf_counter() - t0) * 1000
        log.debug(f"[识别完成] 总耗时 {elapsed:.0f}ms")

        return artifact

    # ---------- OCR 结果解析 ----------

    @staticmethod
    def _extract_roi_texts(
        ocr_result, y_start: int, y_end: int
    ) -> list[str]:
        """从批量 OCR 结果中提取指定 Y 坐标范围内的文本。

        用于 Batch OCR 模式：所有 ROI 拼接为一张图后 OCR，
        再按各 ROI 的 Y 偏移拆分结果。
        """
        texts: list[str] = []
        if not ocr_result or not ocr_result[0]:
            return texts
        result = ocr_result[0]
        if isinstance(result, dict):
            rec_texts = result.get("rec_texts", [])
            dt_polys = result.get("dt_polys", [])
            for text, poly in zip(rec_texts, dt_polys):
                if not text or not text.strip():
                    continue
                if poly is not None and len(poly) > 0:
                    cy = sum(p[1] for p in poly) / len(poly)
                    if y_start <= cy <= y_end:
                        texts.append(text)
        elif isinstance(result, list):
            for line_info in result:
                if not isinstance(line_info, (list, tuple)) or len(line_info) < 2:
                    continue
                poly = line_info[0]
                text_info = line_info[1]
                text = text_info[0] if isinstance(text_info, (list, tuple)) else str(text_info)
                if not text or not text.strip():
                    continue
                if poly is not None and len(poly) > 0:
                    cy = sum(p[1] for p in poly) / len(poly)
                    if y_start <= cy <= y_end:
                        texts.append(text)
        return texts

    @staticmethod
    def _parse_ocr_result(ocr_result) -> tuple[list[str], int]:
        """解析 PaddleOCR 返回结果，提取文本列表和检测框数量"""
        texts: list[str] = []
        dt_count = 0
        if ocr_result and ocr_result[0]:
            result = ocr_result[0]
            if isinstance(result, dict):
                texts = [t for t in result.get("rec_texts", []) if t and t.strip()]
                dt_count = len(result.get("dt_polys", []))
            elif hasattr(result, "rec_texts"):
                texts = [t for t in result.rec_texts if t and t.strip()]
                dt_count = (
                    len(result.dt_polys)
                    if hasattr(result, "dt_polys") and result.dt_polys
                    else 0
                )
            elif isinstance(result, list):
                dt_count = len(result)
                for line_info in result:
                    if isinstance(line_info, (list, tuple)) and len(line_info) >= 2:
                        rec = line_info[1]
                        text = rec[0] if isinstance(rec, (list, tuple)) else str(rec)
                    else:
                        text = str(line_info)
                    if text.strip():
                        texts.append(text.strip())
            else:
                log.warning(f"未知 OCR 结果类型: {type(result)}")
        return texts, dt_count

    # ---------- ROI 临时文件（调试用） ----------

    @staticmethod
    def save_roi_temp(roi: np.ndarray, name: str) -> Path:
        """将 ROI numpy 数组保存为临时 PNG 文件，方便 OCR 和肉眼检查"""
        if roi is None or roi.size == 0:
            raise ValueError(f"ROI [{name}] 为空，请检查坐标是否在截图范围内")
        h, w = roi.shape[:2]
        if h < 10 or w < 10:
            raise ValueError(f"ROI [{name}] 尺寸过小 ({w}x{h})，请扩大选区")
        roi_bgr = cv2.cvtColor(roi, cv2.COLOR_RGB2BGR)
        ok, png_bytes = cv2.imencode(".png", roi_bgr)
        if not ok or png_bytes is None:
            raise OSError(f"ROI [{name}] 编码 PNG 失败")
        safe_name = {
            "圣遗物名称": "set_name",
            "部位+主词条": "piece_main",
            "副词条区": "sub_stats",
            "圣遗物等级": "level",
            "圣遗物锁定状态": "lock",
        }.get(name, "roi")
        path = Path(tempfile.gettempdir()) / f"gsdogfood_{safe_name}.png"
        path.write_bytes(png_bytes.tobytes())
        if not path.exists() or path.stat().st_size == 0:
            raise OSError(f"临时文件写入失败: {path}")
        return path