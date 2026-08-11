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
        except Exception:  # noqa: BLE001 — DB 不可用时返回 True
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
        except Exception:  # noqa: BLE001 — 匹配失败时静默返回 None
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
            log.info(
                f"[匹配部位] OCR='{text}' set_id={set_id} "
                f"候选({len(pieces)}个): {piece_names[:5]}{'...' if len(piece_names) > 5 else ''}"
            )
            result = process.extractOne(text, piece_names, scorer=fuzz.partial_ratio)
            if result:
                log.info(f"[匹配部位] 最佳匹配: '{result[0]}' score={result[1]}")
            if result and result[1] >= 75:
                matched = next(p for p in pieces if p["name"] == result[0])
                return {"type": matched["type"], "name": matched["name"]}

            piece_types = list({(p["type"], p["name"]) for p in pieces})
            for pt, pn in piece_types:
                if pt in text:
                    return {"type": pt, "name": pn}
        except Exception:  # noqa: BLE001 — 匹配失败时静默返回 None
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