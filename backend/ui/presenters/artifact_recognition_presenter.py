"""圣遗物识别 Presenter — 截图 → 调用 Recognizer → 格式化展示"""

from __future__ import annotations

import copy
import time

import numpy as np

from backend.automation.ocr_engine import OcrEngine
from backend.automation.recognizer import ArtifactRecognizer
from backend.utils.screen_capture import CaptureResult, ScreenshotCapture


class ArtifactRecognitionPresenter:
    """圣遗物识别业务逻辑，不依赖任何 Qt Widget"""

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
        """同步识别（主线程 OCR），返回 {ocr_lines, structured_lines, display_result}"""
        t0 = time.perf_counter()
        ocr = self._ocr_engine.get()
        db_empty = ArtifactRecognizer.is_db_empty()

        display = copy.copy(self._current_result)
        display.image = self._current_result.image.copy()

        artifact = ArtifactRecognizer.recognize(
            self._current_result.image, roi_spins, ocr
        )
        return self._build_display_result(artifact, roi_spins, display, t0, db_empty)

    # ---------- 异步识别（供 OcrWorker 线程调用） ----------

    @staticmethod
    def create_recognition_task(
        image: np.ndarray,
        roi_spins: dict[str, tuple[int, int, int, int]],
    ):
        """创建一个可在 OcrWorker 线程中执行的任务函数。

        Panel 只需调用此方法获取任务函数，无需了解 recognize_from_image 的签名。
        """
        def task(ocr):
            return ArtifactRecognitionPresenter.recognize_from_image(
                image, roi_spins, ocr
            )

        return task

    @staticmethod
    def recognize_from_image(
        image: np.ndarray,
        roi_configs: dict[str, tuple[int, int, int, int]],
        ocr,
    ) -> dict:
        """纯计算方法：对给定图像执行完整识别流程，可在 OcrWorker 线程中调用。"""
        import time

        from backend.automation.recognizer import ArtifactRecognizer
        from backend.utils.screen_capture import CaptureMethod, CaptureResult

        t0 = time.perf_counter()
        db_empty = ArtifactRecognizer.is_db_empty()

        display = CaptureResult(
            image=image.copy(),
            width=image.shape[1],
            height=image.shape[0],
            method=CaptureMethod.WIN32,
            elapsed_ms=0.0,
        )

        artifact = ArtifactRecognizer.recognize(image, roi_configs, ocr)
        return ArtifactRecognitionPresenter._build_display_result(
            artifact, roi_configs, display, t0, db_empty
        )

    # ---------- 展示结果构建 ----------

    @staticmethod
    def _build_display_result(
        artifact,
        roi_spins: dict[str, tuple[int, int, int, int]],
        display,
        t0: float,
        db_empty: bool,
    ) -> dict:
        """根据识别结果生成 OCR 日志、绘制 ROI 矩形、格式化结构化输出。"""
        lines: list[str] = []
        if db_empty:
            lines.append(
                "[!] 本地圣遗物模板为空，以下为 OCR 原始识别结果，未进行匹配\n"
            )

        # 生成 OCR 调试日志
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

        # 锁定状态
        if artifact.is_locked is True:
            lines.append("[圣遗物锁定状态] 已锁定")
        elif artifact.is_locked is False:
            lines.append("[圣遗物锁定状态] 未锁定")
        else:
            lines.append("[圣遗物锁定状态] 未能识别")

        # 绘制 ROI 矩形
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

    # ---------- 展示格式化 ----------

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