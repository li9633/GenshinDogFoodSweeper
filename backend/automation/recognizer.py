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


class ArtifactRecognizer:
    """圣遗物识别：OCR 解析 + 套装/部位匹配 + 星级颜色分类 + 锁定状态检测"""

    PIECE_TYPES: ClassVar[set[str]] = {"生之花", "死之羽", "时之沙", "空之杯", "理之冠"}

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
    def match_lock_status(full_image: np.ndarray) -> bool | None:
        """用模板匹配检测锁定状态。

        使用 templates.json 中每个模板的专属 region 裁剪截图，
        再在裁剪区域内做多尺度模板匹配，对比锁/解锁得分。
        """
        locked_path = TemplateManager.get_path("圣遗物状态已锁定")
        unlocked_path = TemplateManager.get_path("圣遗物状态已解锁")
        if locked_path is None or unlocked_path is None:
            return None

        locked_region = TemplateManager.get_region("圣遗物状态已锁定")
        unlocked_region = TemplateManager.get_region("圣遗物状态已解锁")

        full_gray = cv2.cvtColor(full_image, cv2.COLOR_RGB2GRAY)

        def _match(
            template_path: Path, region: tuple[int, int, int, int] | None
        ) -> float:
            tmpl = cv2.imread(str(template_path), cv2.IMREAD_GRAYSCALE)
            if tmpl is None:
                return -1.0
            if region:
                rx, ry, rw, rh = region
                search_area = full_gray[ry : ry + rh, rx : rx + rw]
                if (
                    search_area.size == 0
                    or search_area.shape[0] < tmpl.shape[0]
                    or search_area.shape[1] < tmpl.shape[1]
                ):
                    return -1.0
            else:
                search_area = full_gray
            best, _, _, _ = multi_scale_match(search_area, tmpl)
            return best

        locked_score = _match(locked_path, locked_region)
        unlocked_score = _match(unlocked_path, unlocked_region)

        if locked_score < 0 and unlocked_score < 0:
            return None
        if locked_score > unlocked_score and locked_score > 0.6:
            return True
        if unlocked_score > locked_score and unlocked_score > 0.6:
            return False
        return None

    # ---------- 完整识别流水线 ----------

    @staticmethod
    def recognize(
        image: np.ndarray,
        roi_configs: dict[str, tuple[int, int, int, int]],
        ocr,
    ) -> ArtifactInfo:
        """执行完整圣遗物识别流程：OCR → 匹配 → 解析 → 返回 ArtifactInfo

        Args:
            image: 截图 RGB 图像
            roi_configs: {区域名: (x, y, w, h), ...}
            ocr: PaddleOCR 实例

        Returns:
            ArtifactInfo: 包含所有识别结果的结构化对象
        """
        import time

        from utils.artifact_parser import ArtifactTextParser

        from backend.automation.color_sampler import sample_roi_color

        t0 = time.perf_counter()

        ocr_texts: dict[str, list[str]] = {}
        matched_set_name: str | None = None
        matched_set_id: int | None = None
        matched_piece_type: str | None = None
        matched_piece_name: str | None = None
        matched_rarity: int | None = None
        matched_set_rarities: list[str] = []
        piece_from_set_match = False

        db_empty = ArtifactRecognizer.is_db_empty()

        for name, (x, y, w, h) in roi_configs.items():
            roi = image[y : y + h, x : x + w]
            if roi.size == 0:
                continue

            ArtifactRecognizer.save_roi_temp(roi, name)
            ocr_result = ocr.ocr(roi)
            texts, _ = ArtifactRecognizer._parse_ocr_result(ocr_result)
            ocr_texts[name] = texts

            if db_empty:
                continue

            if name == "圣遗物名称" and texts:
                match = ArtifactRecognizer.match_set_name(texts[0])
                if match:
                    matched_set_name = match[0]
                    matched_set_id = match[1]
                    matched_piece_type = match[2]
                    matched_piece_name = match[3]
                    piece_from_set_match = match[2] is not None
                    log.debug(
                        f"[匹配套装] OCR='{texts[0]}' → set_name='{match[0]}' "
                        f"set_id={match[1]} piece_type={match[2]} piece_name={match[3]} "
                        f"score={match[4]:.3f}"
                    )
            elif name == "部位+主词条" and texts and not piece_from_set_match:
                for t in texts:
                    piece = ArtifactRecognizer.match_piece_type(
                        t, set_id=matched_set_id
                    )
                    if piece:
                        matched_piece_type = piece["type"]
                        matched_piece_name = piece["name"]
                        break

        # 星级识别
        if not db_empty and matched_set_id is not None:
            from database.repository.artifact_set_repo import ArtifactSetRepo

            set_obj = ArtifactSetRepo.find_by_id(matched_set_id)
            if set_obj:
                matched_set_rarities = set_obj.rarity
        if "圣遗物星级" in roi_configs:
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

        # 锁定状态
        lock_status = ArtifactRecognizer.match_lock_status(image)

        # 强化材料检测：部位区域识别到材料关键字则提前返回
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

        # 结构化解析
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
        )

        artifact.rarity = matched_rarity
        artifact.set_id = matched_set_id

        elapsed = (time.perf_counter() - t0) * 1000
        log.debug(f"[识别完成] 耗时 {elapsed:.0f}ms")

        return artifact

    # ---------- OCR 结果解析 ----------

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