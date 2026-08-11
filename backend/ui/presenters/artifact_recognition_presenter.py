"""圣遗物识别 Presenter — 截图 → OCR → 匹配 → 格式化，纯业务逻辑"""

from __future__ import annotations

import copy
import time
from typing import ClassVar

import numpy as np
from utils.artifact_parser import ArtifactTextParser
from utils.logger import log

from backend.automation.color_sampler import sample_roi_color
from backend.automation.ocr_engine import OcrEngine
from backend.automation.recognizer import ArtifactRecognizer
from backend.utils.screen_capture import CaptureResult, ScreenshotCapture


class ArtifactRecognitionPresenter:
    """圣遗物识别业务逻辑，不依赖任何 Qt Widget"""

    RARITY_COLORS: ClassVar[tuple[tuple[int, int, int], ...]] = (
        (113, 118, 138),
        (42, 143, 114),
        (81, 127, 203),
        (161, 86, 224),
        (188, 105, 50),
    )

    def __init__(self):
        self._ocr_engine = OcrEngine()
        self._current_result: CaptureResult | None = None

    # ---------- 截图 ----------

    def capture(self) -> CaptureResult:
        cap = ScreenshotCapture()
        self._current_result = cap.capture()
        return self._current_result

    # ---------- 识别 ----------

    def recognize(self, roi_spins: dict[str, tuple[int, int, int, int]]) -> dict:
        """执行完整识别流程，返回 {ocr_lines, structured_lines, display_result}"""
        t0 = time.perf_counter()
        ocr = self._ocr_engine.get()
        lines: list[str] = []

        db_empty = ArtifactRecognizer.is_db_empty()
        if db_empty:
            lines.append(
                "[!] 本地圣遗物模板为空，以下为 OCR 原始识别结果，未进行匹配\n"
            )

        display = copy.copy(self._current_result)
        display.image = self._current_result.image.copy()

        ocr_texts: dict[str, list[str]] = {}
        matched_set_name: str | None = None
        matched_set_id: int | None = None
        matched_piece_type: str | None = None
        matched_piece_name: str | None = None
        matched_rarity: int | None = None
        matched_set_rarities: list[str] = []
        piece_from_set_match = False

        for name, (x, y, w, h) in roi_spins.items():
            roi = self._current_result.image[y : y + h, x : x + w]
            if roi.size == 0:
                lines.append(f"[{name}] 区域无效")
                continue

            roi_path = ArtifactRecognizer.save_roi_temp(roi, name)
            ocr_result = ocr.ocr(roi)
            texts, dt_count = self._parse_ocr_result(ocr_result)

            combined = " | ".join(texts) if texts else "(无文本)"
            ocr_texts[name] = texts
            lines.append(f"[{name}] OCR: {combined}")
            if texts:
                lines.append(f"  → 检测到 {dt_count} 个文本块，识别出 {len(texts)} 个")
            elif dt_count > 0:
                lines.append(f"  → 检测到 {dt_count} 个文本块，但识别失败")
            else:
                lines.append(f"  → 未检测到任何文本（请检查 {roi_path.name}）")

            if db_empty:
                pass
            elif name == "圣遗物名称" and texts:
                match = ArtifactRecognizer.match_set_name(texts[0])
                if match:
                    matched_set_name = match[0]
                    matched_set_id = match[1]
                    matched_piece_type = match[2]
                    matched_piece_name = match[3]
                    piece_from_set_match = match[2] is not None
                    lines.append(f"  → 匹配套装: {match[0]} (置信度: {match[4]:.0%})")
                    if piece_from_set_match:
                        lines.append(
                            f"  → 部位已确定: {matched_piece_type} ({matched_piece_name})"
                        )
                    log.info(
                        f"[匹配套装] OCR='{texts[0]}' → set_name='{match[0]}' "
                        f"set_id={match[1]} piece_type={match[2]} piece_name={match[3]} "
                        f"score={match[4]:.3f}"
                    )
                else:
                    lines.append("  → 未匹配到套装")
            elif name == "部位+主词条" and texts and not piece_from_set_match:
                    for t in texts:
                        piece = ArtifactRecognizer.match_piece_type(
                            t, set_id=matched_set_id
                        )
                        if piece:
                            matched_piece_type = piece["type"]
                            matched_piece_name = piece["name"]
                            detail = piece["type"]
                            if piece["name"]:
                                detail += f" ({piece['name']})"
                            lines.append(f"  → 匹配部位: {detail}")
                            break
                    else:
                        lines.append("  → 未匹配到部位")

            color = (0, 255, 0) if "→ 匹配" in "\n".join(lines) else (255, 165, 0)
            display.draw_rect(x, y, w, h, color=color, thickness=2, label=name)

        # 星级识别
        if not db_empty and matched_set_id is not None:
            from database.repository.artifact_set_repo import ArtifactSetRepo

            set_obj = ArtifactSetRepo.find_by_id(matched_set_id)
            if set_obj:
                matched_set_rarities = set_obj.rarity
        if "圣遗物星级" in roi_spins:
            sx, sy, sw, sh = roi_spins["圣遗物星级"]
            star_roi = self._current_result.image[sy : sy + sh, sx : sx + sw]
            if star_roi.size > 0:
                rgb = sample_roi_color(self._current_result.image, sx, sy, sw, sh)
                detected = ArtifactRecognizer.classify_rarity(rgb)
                if detected is not None:
                    if matched_set_rarities:
                        if str(detected) in matched_set_rarities:
                            matched_rarity = detected
                            lines.append(
                                f"[星级] {detected}★ (套装允许: {matched_set_rarities})"
                            )
                        else:
                            lines.append(
                                f"[星级] {detected}★ (与套装允许 {matched_set_rarities} 不符，已忽略)"
                            )
                    else:
                        matched_rarity = detected
                        lines.append(f"[星级] {detected}★")
                else:
                    lines.append(f"[星级] 颜色采样失败: RGB{rgb}")

        # 锁定状态
        lock_status = ArtifactRecognizer.match_lock_status(self._current_result.image)
        if lock_status is True:
            lines.append("[圣遗物锁定状态] 已锁定")
        elif lock_status is False:
            lines.append("[圣遗物锁定状态] 未锁定")
        else:
            lines.append("[圣遗物锁定状态] 未能识别")

        # 结构化解析
        name_ocr = " | ".join(ocr_texts.get("圣遗物名称", []))
        main_ocr = " | ".join(ocr_texts.get("部位+主词条", []))
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

        structured_lines = self._format_structured(artifact, matched_rarity)
        elapsed = (time.perf_counter() - t0) * 1000
        lines.append(f"\n总耗时: {elapsed:.0f}ms")

        return {
            "ocr_lines": lines,
            "structured_lines": structured_lines,
            "display_result": display,
            "elapsed_ms": elapsed,
            "db_empty": db_empty,
        }

    # ---------- 异步识别（供 OcrWorker 线程调用） ----------

    @staticmethod
    def recognize_from_image(
        image: np.ndarray,
        roi_configs: dict[str, tuple[int, int, int, int]],
        ocr,
    ) -> dict:
        """纯计算方法：对给定图像执行完整识别流程，可在 OcrWorker 线程中调用。"""
        import time

        from utils.artifact_parser import ArtifactTextParser

        from backend.automation.color_sampler import sample_roi_color
        from backend.automation.recognizer import ArtifactRecognizer
        from backend.utils.screen_capture import CaptureMethod, CaptureResult

        t0 = time.perf_counter()
        lines: list[str] = []

        db_empty = ArtifactRecognizer.is_db_empty()
        if db_empty:
            lines.append(
                "[!] 本地圣遗物模板为空，以下为 OCR 原始识别结果，未进行匹配\n"
            )

        display = CaptureResult(
            image=image.copy(),
            width=image.shape[1],
            height=image.shape[0],
            method=CaptureMethod.WIN32,
            elapsed_ms=0.0,
        )

        ocr_texts: dict[str, list[str]] = {}
        matched_set_name: str | None = None
        matched_set_id: int | None = None
        matched_piece_type: str | None = None
        matched_piece_name: str | None = None
        matched_rarity: int | None = None
        matched_set_rarities: list[str] = []
        piece_from_set_match = False

        for name, (x, y, w, h) in roi_configs.items():
            roi = image[y : y + h, x : x + w]
            if roi.size == 0:
                lines.append(f"[{name}] 区域无效")
                continue

            roi_path = ArtifactRecognizer.save_roi_temp(roi, name)
            ocr_result = ocr.ocr(roi)
            texts, dt_count = ArtifactRecognitionPresenter._parse_ocr_result(
                ocr_result
            )

            combined = " | ".join(texts) if texts else "(无文本)"
            ocr_texts[name] = texts
            lines.append(f"[{name}] OCR: {combined}")
            if texts:
                lines.append(
                    f"  → 检测到 {dt_count} 个文本块，识别出 {len(texts)} 个"
                )
            elif dt_count > 0:
                lines.append(f"  → 检测到 {dt_count} 个文本块，但识别失败")
            else:
                lines.append(f"  → 未检测到任何文本（请检查 {roi_path.name}）")

            if db_empty:
                pass
            elif name == "圣遗物名称" and texts:
                match = ArtifactRecognizer.match_set_name(texts[0])
                if match:
                    matched_set_name = match[0]
                    matched_set_id = match[1]
                    matched_piece_type = match[2]
                    matched_piece_name = match[3]
                    piece_from_set_match = match[2] is not None
                    lines.append(
                        f"  → 匹配套装: {match[0]} (置信度: {match[4]:.0%})"
                    )
                    if piece_from_set_match:
                        lines.append(
                            f"  → 部位已确定: {matched_piece_type} ({matched_piece_name})"
                        )
                    log.info(
                        f"[匹配套装] OCR='{texts[0]}' → set_name='{match[0]}' "
                        f"set_id={match[1]} piece_type={match[2]} piece_name={match[3]} "
                        f"score={match[4]:.3f}"
                    )
                else:
                    lines.append("  → 未匹配到套装")
            elif name == "部位+主词条" and texts and not piece_from_set_match:
                for t in texts:
                    piece = ArtifactRecognizer.match_piece_type(
                        t, set_id=matched_set_id
                    )
                    if piece:
                        matched_piece_type = piece["type"]
                        matched_piece_name = piece["name"]
                        detail = piece["type"]
                        if piece["name"]:
                            detail += f" ({piece['name']})"
                        lines.append(f"  → 匹配部位: {detail}")
                        break
                else:
                    lines.append("  → 未匹配到部位")

            color = (0, 255, 0) if "→ 匹配" in "\n".join(lines) else (255, 165, 0)
            display.draw_rect(x, y, w, h, color=color, thickness=2, label=name)

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
                            lines.append(
                                f"[星级] {detected}★ (套装允许: {matched_set_rarities})"
                            )
                        else:
                            lines.append(
                                f"[星级] {detected}★ (与套装允许 {matched_set_rarities} 不符，已忽略)"
                            )
                    else:
                        matched_rarity = detected
                        lines.append(f"[星级] {detected}★")
                else:
                    lines.append(f"[星级] 颜色采样失败: RGB{rgb}")

        # 锁定状态
        lock_status = ArtifactRecognizer.match_lock_status(image)
        if lock_status is True:
            lines.append("[圣遗物锁定状态] 已锁定")
        elif lock_status is False:
            lines.append("[圣遗物锁定状态] 未锁定")
        else:
            lines.append("[圣遗物锁定状态] 未能识别")

        # 结构化解析
        name_ocr = " | ".join(ocr_texts.get("圣遗物名称", []))
        main_ocr = " | ".join(ocr_texts.get("部位+主词条", []))
        sub_ocr = " | ".join(ocr_texts.get("副词条区", []))
        level_ocr = " | ".join(ocr_texts.get("圣遗物等级", []))
        lock_ocr = (
            "锁定"
            if lock_status is True
            else ("解锁" if lock_status is False else "")
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

        structured_lines = ArtifactRecognitionPresenter._format_structured(
            artifact, matched_rarity
        )
        elapsed = (time.perf_counter() - t0) * 1000
        lines.append(f"\n总耗时: {elapsed:.0f}ms")

        return {
            "ocr_lines": lines,
            "structured_lines": structured_lines,
            "display_result": display,
            "elapsed_ms": elapsed,
            "db_empty": db_empty,
        }

    # ---------- 内部方法 ----------

    @staticmethod
    def _parse_ocr_result(ocr_result) -> tuple[list[str], int]:
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

    @staticmethod
    def _format_structured(artifact, rarity: int | None) -> list[str]:
        lines: list[str] = []
        lines.append("【结构化解析结果】")
        lines.append(f"  套装: {artifact.set_name or '未识别'}")
        if artifact.set_effects:
            for key in ("1pc", "2pc", "4pc"):
                if key in artifact.set_effects:
                    label = {"1pc": "1件套", "2pc": "2件套", "4pc": "4件套"}[key]
                    lines.append(f"    {label}: {artifact.set_effects[key]}")
        if artifact.level is not None:
            lines.append(f"  等级: +{artifact.level}")
        if artifact.is_locked is not None:
            lines.append(f"  锁定: {'是' if artifact.is_locked else '否'}")
        if artifact.piece_type:
            detail = artifact.piece_type
            if artifact.piece_name:
                detail += f" ({artifact.piece_name})"
            lines.append(f"  部位: {detail}")
        if rarity is not None:
            lines.append(f"  星级: {rarity}★")
        if artifact.main_stat:
            ms = artifact.main_stat
            pct = "%" if ms.is_percentage else ""
            lines.append(f"  主词条: {ms.name} +{ms.value}{pct}")
        if artifact.sub_stats:
            lines.append("  副词条:")
            for ss in artifact.sub_stats:
                pct = "%" if ss.is_percentage else ""
                lock = " (待激活)" if ss.is_locked else ""
                lines.append(f"    • {ss.name} +{ss.value}{pct}{lock}")
        else:
            lines.append("  副词条: 未解析到")
        return lines