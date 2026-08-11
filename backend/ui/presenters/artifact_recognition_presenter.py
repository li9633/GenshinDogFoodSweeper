"""圣遗物识别 Presenter — QObject 封装，供 QML 绑定

截图 → OCR → Recognizer → 格式化展示。
"""

from __future__ import annotations

import copy
import json
import time

import numpy as np
from PySide6.QtCore import Property, QObject, Signal, Slot

from backend.automation.ocr_engine import OcrEngine
from backend.automation.recognizer import ArtifactRecognizer
from backend.utils.screen_capture import CaptureResult, ScreenshotCapture

from .image_provider import PreviewImageProvider


class ArtifactRecognitionPresenter(QObject):
    """圣遗物识别 Presenter — QML 可绑定"""

    # -- 信号 --
    recognitionStarted = Signal()
    recognitionFinished = Signal(str, str, str, bool)
    # ocrText, structuredText, imagePath
    errorOccurred = Signal(str)
    clearPreview = Signal()
    textChanged = Signal()
    recognizingChanged = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._ocr_engine = OcrEngine()
        self._current_result: CaptureResult | None = None
        self._ocr_text = ""
        self._structured_text = ""
        self._recognizing = False

    @Property(str, notify=textChanged)
    def ocrText(self) -> str:
        return self._ocr_text

    @Property(str, notify=textChanged)
    def structuredText(self) -> str:
        return self._structured_text

    @Property(bool, notify=recognizingChanged)
    def recognizing(self) -> bool:
        return self._recognizing

    # ========== 识别 ==========

    @Slot(str)
    def recognize(self, roi_json: str) -> None:
        """截图 → OCR → 识别，结果通过信号返回"""
        self._recognizing = True
        self.recognizingChanged.emit()
        self.recognitionStarted.emit()

        try:
            roi_list = json.loads(roi_json)
            roi_spins: dict[str, tuple[int, int, int, int]] = {}
            for item in roi_list:
                roi_spins[item["name"]] = (
                    int(item["x"]), int(item["y"]),
                    int(item["w"]), int(item["h"]),
                )

            cap = ScreenshotCapture()
            self._current_result = cap.capture()

            t0 = time.perf_counter()
            ocr = self._ocr_engine.get()
            db_empty = ArtifactRecognizer.is_db_empty()

            display = copy.copy(self._current_result)
            display.image = self._current_result.image.copy()

            artifact = ArtifactRecognizer.recognize(
                self._current_result.image, roi_spins, ocr
            )
            result = self._build_display_result(
                artifact, roi_spins, display, t0, db_empty
            )

            self._ocr_text = "\n".join(result["ocr_lines"])
            self._structured_text = "\n".join(result["structured_lines"])
            self.textChanged.emit()

            # 保存结果图（内存缓存，零 IO）
            PreviewImageProvider.put("artifact", result["display_result"].image)

            self.recognitionFinished.emit(
                self._ocr_text, self._structured_text, "artifact", db_empty
            )

        except Exception as exc:
            self.errorOccurred.emit(str(exc))
        finally:
            self._recognizing = False
            self.recognizingChanged.emit()

    @Slot()
    def clear(self) -> None:
        self._ocr_text = ""
        self._structured_text = ""
        self._current_result = None
        self.textChanged.emit()
        PreviewImageProvider.clear("artifact")
        self.clearPreview.emit()

    # ========== 展示结果构建 ==========

    @staticmethod
    def _build_display_result(
        artifact,
        roi_spins: dict[str, tuple[int, int, int, int]],
        display,
        t0: float,
        db_empty: bool,
    ) -> dict:
        lines: list[str] = []
        if db_empty:
            lines.append(
                "[!] 本地圣遗物模板为空，以下为 OCR 原始识别结果，未进行匹配\n"
            )

        for name in roi_spins:
            if name == "圣遗物星级":
                if artifact.rarity is not None:
                    lines.append(f"[星级] {artifact.rarity}★")
                else:
                    lines.append("[星级] 未能识别")
            else:
                raw = artifact.raw_texts.get(name, "")
                combined = raw if raw else "(无文本)"
                lines.append(f"[{name}] OCR: {combined}")

        if artifact.is_locked is True:
            lines.append("[圣遗物锁定状态] 已锁定")
        elif artifact.is_locked is False:
            lines.append("[圣遗物锁定状态] 未锁定")
        else:
            lines.append("[圣遗物锁定状态] 未能识别")

        has_match = bool(artifact.set_name or artifact.piece_type)
        for name, (x, y, w, h) in roi_spins.items():
            color = (0, 255, 0) if has_match else (255, 165, 0)
            display.draw_rect(x, y, w, h, color=color, thickness=2, label=name)

        structured_lines = ArtifactRecognitionPresenter._format_structured(artifact)
        elapsed = (time.perf_counter() - t0) * 1000
        lines.append(f"\n总耗时: {elapsed:.0f}ms")

        return {
            "ocr_lines": lines,
            "structured_lines": structured_lines,
            "display_result": display,
            "elapsed_ms": elapsed,
            "db_empty": db_empty,
        }

    @staticmethod
    def _format_structured(artifact) -> list[str]:
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
        if artifact.rarity is not None:
            lines.append(f"  星级: {artifact.rarity}★")
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