"""圣遗物识别 Presenter — QObject 封装，供 QML 绑定

截图 → OCR → Recognizer → 格式化展示。

OCR 识别通过 OcrWorker 在专用线程中执行，避免阻塞 UI。
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np
from PySide6.QtCore import Property, QObject, Signal, Slot
from utils.logger import log

from backend.automation.recognizer import ArtifactRecognizer
from backend.automation.roi_config import ANCHOR_ROI_DEFINITIONS
from backend.utils.screen_capture import CaptureMethod, CaptureResult, ScreenshotCapture

from .image_provider import PreviewImageProvider


@dataclass
class RoiDefinition:
    """单个 ROI 区域定义 DTO"""
    name: str
    dx: int
    dy: int
    dw: int
    dh: int

    def to_dict(self) -> dict:
        return {"name": self.name, "dx": self.dx, "dy": self.dy, "dw": self.dw, "dh": self.dh}


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
    roiDefinitionsChanged = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._current_result: CaptureResult | None = None
        self._ocr_text = ""
        self._structured_text = ""
        self._recognizing = False
        self._roi_definitions: list[RoiDefinition] = [
            RoiDefinition(name, dx, dy, dw, dh)
            for name, dx, dy, dw, dh in ANCHOR_ROI_DEFINITIONS
        ]
        self._connect_ocr_worker()

    @Property(str, notify=textChanged)
    def ocrText(self) -> str:
        return self._ocr_text

    @Property(str, notify=textChanged)
    def structuredText(self) -> str:
        return self._structured_text

    @Property(bool, notify=recognizingChanged)
    def recognizing(self) -> bool:
        return self._recognizing

    @Property(list, notify=roiDefinitionsChanged)
    def roiDefinitions(self) -> list[dict]:
        return [r.to_dict() for r in self._roi_definitions]

    @Slot(int, int, int, int, int)
    def updateRoi(self, index: int, x: int, y: int, w: int, h: int) -> None:
        if 0 <= index < len(self._roi_definitions):
            r = self._roi_definitions[index]
            r.dx = x
            r.dy = y
            r.dw = w
            r.dh = h

    # ========== 识别 ==========

    @Slot()
    def recognize(self) -> None:
        """截图 → 提交 OCR Worker → 结果通过信号返回（不阻塞 UI）"""
        self._recognizing = True
        self.recognizingChanged.emit()
        self.recognitionStarted.emit()

        try:
            roi_spins: dict[str, tuple[int, int, int, int]] = {
                r.name: (r.dx, r.dy, r.dw, r.dh) for r in self._roi_definitions
            }

            cap = ScreenshotCapture()
            self._current_result = cap.capture()

            task_fn = ArtifactRecognitionPresenter.create_recognition_task(
                self._current_result.image.copy(), roi_spins
            )

            from backend.automation.ocr_worker import OcrWorker

            worker = OcrWorker.instance()
            worker.submit(task_fn, callback_data=None)

        except Exception as exc:
            self._on_recognize_error(str(exc))

    # ---------- OCR Worker 信号连接 ----------

    def _connect_ocr_worker(self) -> None:
        from backend.automation.ocr_worker import OcrWorker

        worker = OcrWorker.instance()
        worker.task_done.connect(self._on_ocr_task_done)
        worker.task_error.connect(self._on_ocr_task_error)

    def _on_ocr_task_done(self, result: dict, _callback_data: object) -> None:
        if not isinstance(result, dict):
            return
        if "ocr_lines" not in result:
            return
        data = result
        self._ocr_text = "\n".join(data["ocr_lines"])
        self._structured_text = "\n".join(data["structured_lines"])
        self.textChanged.emit()

        PreviewImageProvider.put("artifact", data["display_result"].image)

        elapsed = data.get("elapsed_ms", 0)
        log.info(f"圣遗物识别完成 ({elapsed:.0f}ms)")

        self.recognitionFinished.emit(
            self._ocr_text,
            self._structured_text,
            "artifact",
            data.get("db_empty", False),
        )
        self._recognizing = False
        self.recognizingChanged.emit()

    def _on_ocr_task_error(self, error: str, _callback_data: object) -> None:
        self._on_recognize_error(error)

    def _on_recognize_error(self, error: str) -> None:
        log.error(f"圣遗物识别失败: {error}")
        self.errorOccurred.emit(str(error))
        self._recognizing = False
        self.recognizingChanged.emit()

    # ---------- OCR 任务工厂 ----------

    @staticmethod
    def create_recognition_task(
        image: np.ndarray,
        roi_configs: dict[str, tuple[int, int, int, int]],
    ) -> Callable[[Any], dict]:
        """创建 OCR 识别任务（在 Worker 线程中执行）。

        Args:
            image: 截图 RGB 图像
            roi_configs: {区域名: (x, y, w, h), ...}

        Returns:
            callable(ocr_instance) -> dict，包含 ocr_lines / structured_lines /
            display_result / elapsed_ms / db_empty
        """

        def task(ocr) -> dict:
            t0 = time.perf_counter()
            db_empty = ArtifactRecognizer.is_db_empty()

            artifact = ArtifactRecognizer.recognize(image, roi_configs, ocr)

            display = CaptureResult(
                image=image.copy(),
                width=image.shape[1],
                height=image.shape[0],
                method=CaptureMethod.WIN32,
                elapsed_ms=0,
            )

            return ArtifactRecognitionPresenter._build_display_result(
                artifact, roi_configs, display, t0, db_empty
            )

        return task

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