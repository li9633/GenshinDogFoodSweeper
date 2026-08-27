"""圣遗物识别 Presenter — QObject 封装，供 QML 绑定

截图 → OCR → Recognizer → 格式化展示。

OCR 识别通过 OcrWorker 在专用线程中执行，避免阻塞 UI。
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot
from utils.logger import log

from backend.automation.recognizer import ArtifactRecognizer
from backend.models.slot_models import ALL_SLOT_CONFIGS, SlotDetectorConfig
from backend.utils.screen_capture import CaptureMethod, CaptureResult, ScreenshotCapture

from .image_provider import PreviewImageProvider


class ArtifactRecognitionPresenter(QObject):
    """圣遗物识别 Presenter — QML 可绑定

    截图 → OCR → Recognizer → 格式化展示。
    ROI 坐标从当前选中的 SlotDetectorConfig.detail_roi_configs 获取，
    支持切换配置（背包/分解页面）快速调试。
    """

    # -- 信号 --
    recognitionStarted = Signal()
    recognitionFinished = Signal(str, str, str, bool)
    # ocrText, structuredText, imagePath
    errorOccurred = Signal(str)
    clearPreview = Signal()
    textChanged = Signal()
    recognizingChanged = Signal()
    activeConfigChanged = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._current_result = None
        self._ocr_text = ""
        self._structured_text = ""
        self._recognizing = False
        self._result_db_empty = False
        self._last_preview_key = "artifact"
        self._available_configs = list(ALL_SLOT_CONFIGS)
        self._active_config: SlotDetectorConfig = self._available_configs[0]
        self._active_config_index = 0
        self._result_timer = QTimer(self)
        self._result_timer.setSingleShot(True)
        self._result_timer.timeout.connect(self._emit_recognition_finished)
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

    # ========== 检测配置切换 ==========

    @Property("QVariantList", notify=activeConfigChanged)
    def availableConfigNames(self) -> list[str]:
        return [c.name for c in self._available_configs]

    @Property(int, notify=activeConfigChanged)
    def activeConfigIndex(self) -> int:
        return self._active_config_index

    @Property(str, notify=activeConfigChanged)
    def activeConfigName(self) -> str:
        return self._active_config.name

    @Property(str, notify=activeConfigChanged)
    def activeConfigDetail(self) -> str:
        """当前配置摘要：行×列、是否显示数量、格子 ROI"""
        c = self._active_config
        roi = c.roi
        count_info = "有数量" if c.has_artifact_count else "无数量"
        return (
            f"格子: {c.rows}行×{c.cols}列 | {count_info}\n"
            f"格子ROI: ({roi[0]}, {roi[1]}, {roi[2]}×{roi[3]})"
        )

    @Slot(int)
    def setActiveConfigByIndex(self, index: int) -> None:
        if 0 <= index < len(self._available_configs):
            self._active_config = self._available_configs[index]
            self._active_config_index = index
            log.info(f"圣遗物识别配置切换: {self._active_config.name}")
            self.activeConfigChanged.emit()

    # ========== 识别 ==========

    @Slot()
    def recognize(self) -> None:
        """截图 → 提交 OCR Worker → 结果通过信号返回（不阻塞 UI）"""
        self._recognizing = True
        self.recognizingChanged.emit()
        self.recognitionStarted.emit()

        try:
            roi_spins = self._active_config.detail_roi_configs

            t_capture = time.perf_counter()
            cap = ScreenshotCapture()
            self._current_result = cap.capture()
            log.debug(
                f"[耗时] 截图捕获: {(time.perf_counter() - t_capture) * 1000:.1f}ms "
                f"(尺寸{self._current_result.width}x{self._current_result.height})"
            )

            task_fn = ArtifactRecognitionPresenter.create_recognition_task(
                self._current_result.image.copy(),
                roi_spins,
                lock_anchor_search_region=self._active_config.lock_anchor_search_region,
                lock_anchor_to_level=self._active_config.lock_anchor_to_level,
                lock_anchor_to_sub_stats=self._active_config.lock_anchor_to_sub_stats,
            )

            from backend.automation.ocr_worker import OcrWorker

            worker = OcrWorker.instance()
            worker.submit(task_fn, callback_data=None)

        except Exception:
            self._recognizing = False
            self.recognizingChanged.emit()
            raise

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

        self._last_preview_key = PreviewImageProvider.put("artifact", data["display_result"].image)

        elapsed = data.get("elapsed_ms", 0)
        log.info(f"圣遗物识别完成 ({elapsed:.0f}ms)")

        self._result_db_empty = data.get("db_empty", False)
        self._result_timer.start(0)
        self._recognizing = False
        self.recognizingChanged.emit()

    def _on_ocr_task_error(self, error: str, _callback_data: object) -> None:
        self._on_recognize_error(error)

    def _emit_recognition_finished(self) -> None:
        self.recognitionFinished.emit(
            self._ocr_text,
            self._structured_text,
            self._last_preview_key,
            self._result_db_empty,
        )

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
        lock_anchor_search_region: tuple[int, int, int, int] | None = None,
        lock_anchor_to_level: tuple[int, int, int, int] | None = None,
        lock_anchor_to_sub_stats: tuple[int, int, int, int] | None = None,
    ) -> Callable[[Any], dict]:
        """创建 OCR 识别任务（在 Worker 线程中执行）。

        Args:
            image: 截图 RGB 图像
            roi_configs: {区域名: (x, y, w, h), ...}
            lock_anchor_*: 锁定图标锚点定位参数，用于调试绘制

        Returns:
            callable(ocr_instance) -> dict，包含 ocr_lines / structured_lines /
            display_result / elapsed_ms / db_empty
        """

        def task(ocr) -> dict:
            t0 = time.perf_counter()
            db_empty = ArtifactRecognizer.is_db_empty()

            artifact = ArtifactRecognizer.recognize(
                image, roi_configs, ocr,
                lock_anchor_search_region=lock_anchor_search_region,
                lock_anchor_to_level=lock_anchor_to_level,
                lock_anchor_to_sub_stats=lock_anchor_to_sub_stats,
            )

            t_build = time.perf_counter()
            display = CaptureResult(
                image=image.copy(),
                width=image.shape[1],
                height=image.shape[0],
                method=CaptureMethod.WIN32,
                elapsed_ms=0,
            )

            result = ArtifactRecognitionPresenter._build_display_result(
                artifact, roi_configs, display, t0, db_empty,
                lock_anchor_search_region=lock_anchor_search_region,
                lock_anchor_to_level=lock_anchor_to_level,
                lock_anchor_to_sub_stats=lock_anchor_to_sub_stats,
            )
            log.debug(
                f"[耗时] 展示结果构建: {(time.perf_counter() - t_build) * 1000:.1f}ms"
            )
            return result

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
    def _draw_dashed_rect(
        img: np.ndarray,
        x: int, y: int, w: int, h: int,
        color: tuple[int, int, int],
        dash: int = 8,
    ) -> None:
        """在 BGR 图像上绘制虚线矩形框。"""
        for i in range(0, w, dash * 2):
            x1 = x + i
            x2 = min(x + i + dash, x + w)
            cv2.line(img, (x1, y), (x2, y), color, 1)
            cv2.line(img, (x1, y + h), (x2, y + h), color, 1)
        for i in range(0, h, dash * 2):
            y1 = y + i
            y2 = min(y + i + dash, y + h)
            cv2.line(img, (x, y1), (x, y2), color, 1)
            cv2.line(img, (x + w, y1), (x + w, y2), color, 1)

    @staticmethod
    def _build_display_result(
        artifact,
        roi_spins: dict[str, tuple[int, int, int, int]],
        display,
        t0: float,
        db_empty: bool,
        lock_anchor_search_region: tuple[int, int, int, int] | None = None,
        lock_anchor_to_level: tuple[int, int, int, int] | None = None,
        lock_anchor_to_sub_stats: tuple[int, int, int, int] | None = None,
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
        # 批量绘制：一次 RGB→BGR，画所有矩形和标签，再转回 RGB
        t_draw = time.perf_counter()
        img_bgr = cv2.cvtColor(display.image, cv2.COLOR_RGB2BGR)
        for name, (x, y, w, h) in roi_spins.items():
            bgr = (0, 255, 0) if has_match else (255, 165, 0)
            cv2.rectangle(img_bgr, (x, y), (x + w, y + h), bgr, thickness=2)
        # 用 PIL 统一绘制中文标签（只加载一次字体）
        from PIL import Image, ImageDraw, ImageFont

        rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb)
        draw = ImageDraw.Draw(pil_img)
        font = None
        for fp in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf"):
            if Path(fp).exists():
                font = ImageFont.truetype(fp, 18)
                break
        if font:
            for name, (x, y, _, _) in roi_spins.items():
                bgr = (0, 255, 0) if has_match else (255, 165, 0)
                draw.text((x, y - 6), name, font=font, fill=bgr[::-1])
            img_bgr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

        # 锁定图标锚点调试：画搜索区域、锁位置、偏移ROI、连线
        if lock_anchor_to_level is not None or lock_anchor_to_sub_stats is not None:
            # 搜索区域（黄色虚线框）—— 始终绘制，方便直观看到模板匹配的搜索范围
            from backend.automation.template_manager import TemplateManager

            sr_template = TemplateManager.get("圣遗物状态已解锁")
            sr = lock_anchor_search_region or (sr_template.region if sr_template else None)
            if sr:
                sx, sy, sw, sh = sr
                ArtifactRecognitionPresenter._draw_dashed_rect(
                    img_bgr, sx, sy, sw, sh, (0, 255, 255), dash=8
                )
                # 搜索区域标签
                if font:
                    draw.text((sx, sy - 6), "锁搜索区", font=font, fill=(0, 255, 255))

            lock_pos = ArtifactRecognizer.find_lock_icon_position(
                display.image, lock_anchor_search_region
            )
            if lock_pos is not None:
                lx, ly = lock_pos
                # 锁定图标位置（红色十字，画在匹配区域中心）
                # 蓝色矩形框：标记模板匹配返回的实际锁图标尺寸
                lock_cx = lock_cy = 0
                for key in ("圣遗物状态已解锁", "圣遗物状态已锁定"):
                    t = TemplateManager.get(key)
                    if t:
                        tmpl = cv2.imread(str(t.path))
                        if tmpl is not None:
                            th, tw = tmpl.shape[:2]
                            cv2.rectangle(
                                img_bgr,
                                (lx, ly),
                                (lx + tw, ly + th),
                                (255, 0, 0), 2,
                            )
                            lock_cx = lx + tw // 2
                            lock_cy = ly + th // 2
                            break
                cv2.drawMarker(img_bgr, (lock_cx, lock_cy), (0, 0, 255), cv2.MARKER_CROSS, 12, 2)
                # 偏移ROI（绿色实线框）
                if lock_anchor_to_level is not None:
                    dx, dy, dw, dh = lock_anchor_to_level
                    cv2.rectangle(img_bgr, (lx + dx, ly + dy), (lx + dx + dw, ly + dy + dh), (0, 255, 0), 2)
                    # 锁→等级 连线
                    cv2.line(img_bgr, (lock_cx, lock_cy), (lx + dx + dw // 2, ly + dy + dh // 2), (0, 0, 255), 1)
                if lock_anchor_to_sub_stats is not None:
                    dx, dy, dw, dh = lock_anchor_to_sub_stats
                    lvl_x, lvl_y = roi_spins.get("圣遗物等级", (lx, ly))[:2]
                    sx, sy = lvl_x + dx, lvl_y + dy
                    cv2.rectangle(img_bgr, (sx, sy), (sx + dw, sy + dh), (0, 255, 0), 2)
                    # 等级→副词条 连线
                    cv2.line(img_bgr, (lvl_x + roi_spins["圣遗物等级"][2] // 2, lvl_y + roi_spins["圣遗物等级"][3]),
                             (sx + dw // 2, sy), (255, 0, 0), 1)

        display.image = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        log.debug(
            f"[耗时] 绘制标注框: {(time.perf_counter() - t_draw) * 1000:.1f}ms"
        )

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
                lock = " (待激活)" if ss.is_activated else ""
                lines.append(f"    • {ss.name} +{ss.value}{pct}{lock}")
        else:
            lines.append("  副词条: 未解析到")
        return lines