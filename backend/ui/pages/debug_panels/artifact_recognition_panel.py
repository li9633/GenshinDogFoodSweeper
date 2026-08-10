"""圣遗物识别调试面板 — OCR + BBS 数据匹配"""

from __future__ import annotations

import copy
import os
import time
from pathlib import Path
from typing import ClassVar

# 必须在任何 paddle 相关 import 之前设置，禁用 oneDNN+PIR 避免推理错误
os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
os.environ["FLAGS_use_onednn"] = "False"
os.environ["FLAGS_use_mkldnn"] = "0"
os.environ["FLAGS_enable_pir_api"] = "False"

import cv2
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from utils.logger import log

from backend.utils.screen_capture import CaptureResult, ScreenshotCapture


class ArtifactRecognitionPanel(QWidget):
    """圣遗物识别调试 — 截图 → OCR → BBS 匹配"""

    PIECE_TYPES: ClassVar[set[str]] = {"生之花", "死之羽", "时之沙", "空之杯", "理之冠"}

    def __init__(self, capture_widget: QWidget | None = None, parent=None):
        super().__init__(parent)
        self._capture_widget = capture_widget
        self._ocr = None
        self._current_result: CaptureResult | None = None
        self._build_ui()

    # ---------- UI ----------

    def _build_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        content = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        content.setLayout(layout)

        # ---- ROI 定义 ----
        roi_group = QGroupBox("ROI 区域定义（相对于游戏窗口）")
        roi_layout = QVBoxLayout()
        roi_layout.setContentsMargins(4, 4, 4, 4)
        roi_layout.setSpacing(2)
        roi_group.setLayout(roi_layout)

        self._roi_spins: dict[str, tuple[QSpinBox, QSpinBox, QSpinBox, QSpinBox]] = {}
        defaults = [
            ("圣遗物名称", (1329, 144, 262, 62)),
            ("部位+主词条", (1339, 214, 160, 174)),
            ("副词条区", (1347, 498, 276, 166)),
        ]
        for name, (dx, dy, dw, dh) in defaults:
            row = QHBoxLayout()
            row.setSpacing(2)
            row.addWidget(QLabel(f"{name}:"))
            spins: list[QSpinBox] = []
            for label_text, val in zip("XYWH", (dx, dy, dw, dh)):
                row.addWidget(QLabel(f"{label_text}:"))
                spin = QSpinBox()
                spin.setRange(0, 9999)
                spin.setValue(val)
                spin.setMinimumWidth(50)
                row.addWidget(spin)
                spins.append(spin)
            self._roi_spins[name] = tuple(spins)  # type: ignore[assignment]
            row.addStretch()
            roi_layout.addLayout(row)

        layout.addWidget(roi_group)

        # ---- 识别结果 ----
        result_group = QGroupBox("识别结果")
        result_layout = QVBoxLayout()
        result_layout.setContentsMargins(4, 4, 4, 4)
        result_layout.setSpacing(3)
        result_group.setLayout(result_layout)

        self._result_text = QTextEdit()
        self._result_text.setReadOnly(True)
        self._result_text.setMaximumHeight(220)
        self._result_text.setPlaceholderText("点击「识别」查看结果…")
        result_layout.addWidget(self._result_text)

        layout.addWidget(result_group)

        # ---- 操作按钮 ----
        btn_row = QHBoxLayout()
        btn_row.setSpacing(3)
        self._btn_capture = QPushButton("截图")
        self._btn_capture.clicked.connect(self._on_capture)
        btn_row.addWidget(self._btn_capture)
        self._btn_recognize = QPushButton("识别")
        self._btn_recognize.setProperty("class", "primary")
        self._btn_recognize.clicked.connect(self._on_recognize)
        btn_row.addWidget(self._btn_recognize)
        self._btn_clear = QPushButton("清除")
        self._btn_clear.clicked.connect(self._on_clear)
        btn_row.addWidget(self._btn_clear)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        scroll.setWidget(content)
        outer_layout.addWidget(scroll)

    # ---------- 截图 ----------

    def _on_capture(self) -> None:
        self._btn_capture.setEnabled(False)
        self._btn_capture.setText("截图中…")
        try:
            cap = ScreenshotCapture()
            self._current_result = cap.capture()
            if self._capture_widget:
                self._capture_widget.display_pixmap(
                    self._current_result.to_qpixmap(), "截图完成"
                )
            log.info("截图完成，点击「识别」开始分析")
        except RuntimeError as e:
            log.error(f"截图失败: {e}")
        finally:
            self._btn_capture.setEnabled(True)
            self._btn_capture.setText("截图")

    # ---------- 识别 ----------

    def _on_recognize(self) -> None:
        if self._current_result is None:
            log.warning("请先截图")
            return

        self._btn_recognize.setEnabled(False)
        self._btn_recognize.setText("识别中…")
        self._result_text.clear()

        try:
            t0 = time.perf_counter()
            ocr = self._get_ocr()
            lines: list[str] = []

            # 检查本地数据库是否为空
            db_empty = self._is_db_empty()
            if db_empty:
                QMessageBox.warning(
                    self,
                    "本地圣遗物模板为空",
                    "数据库中暂无圣遗物套装数据，将仅显示 OCR 识别结果，不进行匹配。\n\n"
                    "请前往[设置]页面，点击「圣遗物同步」拉取最新圣遗物数据。",
                )
                lines.append("⚠ 本地圣遗物模板为空，以下为 OCR 原始识别结果，未进行匹配\n")

            # 复制一份用于绘制 ROI 框
            display = copy.copy(self._current_result)
            display.image = self._current_result.image.copy()

            for name, (sx, sy, sw, sh) in self._roi_spins.items():
                x, y, w, h = sx.value(), sy.value(), sw.value(), sh.value()
                roi = self._current_result.image[y:y + h, x:x + w]
                if roi.size == 0:
                    lines.append(f"[{name}] 区域无效")
                    continue

                # 保存 ROI 为临时文件（PaddleOCR 3.x 对文件路径更稳定）
                roi_path = self._save_roi_temp(roi, name)

                # OCR（直接传 numpy 数组，跳过文件 I/O）
                ocr_result = ocr.ocr(roi)
                texts: list[str] = []
                dt_count = 0
                if ocr_result and ocr_result[0]:
                    result = ocr_result[0]
                    log.info(f'[{name}] OCR result type: {type(result).__name__}, dir: {[a for a in dir(result) if not a.startswith("_")]}')
                    # PaddleOCR 3.x: OCRResult 对象 或 dict
                    if isinstance(result, dict):
                        texts = [t for t in result.get("rec_texts", []) if t and t.strip()]
                        dt_count = len(result.get("dt_polys", []))
                    elif hasattr(result, "rec_texts"):
                        texts = [t for t in result.rec_texts if t and t.strip()]
                        dt_count = len(result.dt_polys) if hasattr(result, "dt_polys") and result.dt_polys else 0
                    # PaddleOCR 2.x: list of [bbox, (text, score)]
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
                        log.warning(f"[{name}] 未知 OCR 结果类型: {type(result)}")

                combined = " | ".join(texts) if texts else "(无文本)"
                lines.append(f"[{name}] OCR: {combined}")
                if texts:
                    lines.append(f"  → 检测到 {dt_count} 个文本块，识别出 {len(texts)} 个")
                elif dt_count > 0:
                    lines.append(f"  → 检测到 {dt_count} 个文本块，但识别失败（可能是字体/颜色问题）")
                else:
                    lines.append(f"  → 未检测到任何文本（坐标可能不对，请检查 {roi_path.name}）")

                # BBS 匹配（数据库为空时跳过）
                if db_empty:
                    pass
                elif name == "圣遗物名称" and texts:
                    match = self._match_set_name(texts[0])
                    if match:
                        lines.append(f"  → 匹配套装: {match[0]} (置信度: {match[1]:.0%})")
                    else:
                        lines.append("  → 未匹配到套装")
                elif name == "部位+主词条" and texts:
                    for t in texts:
                        piece = self._match_piece_type(t)
                        if piece:
                            detail = piece["type"]
                            if piece["name"]:
                                detail += f" ({piece['name']})"
                            lines.append(f"  → 匹配部位: {detail}")
                            break
                    else:
                        lines.append("  → 未匹配到部位")

                # 在预览图上画 ROI 框
                color = (0, 255, 0) if "→ 匹配" in "\n".join(lines) else (255, 165, 0)
                display.draw_rect(x, y, w, h, color=color, thickness=2, label=name)

            elapsed = (time.perf_counter() - t0) * 1000
            lines.append(f"\n总耗时: {elapsed:.0f}ms")
            self._result_text.setText("\n".join(lines))

            # 更新预览（带 ROI 框）
            if self._capture_widget:
                self._capture_widget.display_pixmap(
                    display.to_qpixmap(), f"识别完成 ({elapsed:.0f}ms)"
                )

            log.info(f"识别完成 ({elapsed:.0f}ms)")

        except Exception as e:  # noqa: BLE001 — 顶层兜底，确保 UI 不会崩溃
            log.error(f"识别失败: {e}")
            self._result_text.setText(f"错误: {e}")
        finally:
            self._btn_recognize.setEnabled(True)
            self._btn_recognize.setText("识别")

    # ---------- OCR ----------

    def _get_ocr(self):
        """懒加载 PaddleOCR 实例（移动端模型 + 禁用文档预处理）"""
        if self._ocr is None:
            from paddleocr import PaddleOCR

            log.info("首次加载 OCR 引擎（3-5 秒）…")
            self._ocr = PaddleOCR(
                lang="ch",
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
                text_detection_model_name="PP-OCRv5_mobile_det",
                text_recognition_model_name="PP-OCRv5_mobile_rec",
            )
            log.info("OCR 引擎就绪")
        return self._ocr

    # ---------- BBS 匹配 ----------

    @staticmethod
    def _is_db_empty() -> bool:
        """检查本地圣遗物数据库是否为空"""
        try:
            from database.repository.artifact_set_repo import ArtifactSetRepo
            return ArtifactSetRepo.count() == 0
        except Exception:  # noqa: BLE001 — DB 不可用时返回 True
            return True

    @staticmethod
    def _save_roi_temp(roi, name: str) -> Path:
        """将 ROI numpy 数组保存为临时 PNG 文件，方便 OCR 和肉眼检查"""
        import tempfile
        if roi is None or roi.size == 0:
            raise ValueError(f"ROI [{name}] 为空，请检查坐标是否在截图范围内")
        h, w = roi.shape[:2]
        if h < 10 or w < 10:
            raise ValueError(f"ROI [{name}] 尺寸过小 ({w}x{h})，请扩大选区")
        roi_bgr = cv2.cvtColor(roi, cv2.COLOR_RGB2BGR)
        # cv2.imencode 编码为 PNG 字节，再用 Python 原生写入（避免中文路径 + mkstemp 问题）
        ok, png_bytes = cv2.imencode(".png", roi_bgr)
        if not ok or png_bytes is None:
            raise OSError(f"ROI [{name}] 编码 PNG 失败")
        safe_name = {"圣遗物名称": "set_name", "部位+主词条": "piece_main", "副词条区": "sub_stats"}.get(name, "roi")
        path = Path(tempfile.gettempdir()) / f"gsdogfood_{safe_name}.png"
        path.write_bytes(png_bytes.tobytes())
        if not path.exists() or path.stat().st_size == 0:
            raise OSError(f"临时文件写入失败: {path}")
        return path

    @staticmethod
    def _match_set_name(text: str) -> tuple[str, float] | None:
        """用 OCR 文本匹配圣遗物套装。

        优先匹配 artifact_pieces.name（部位单件名），再通过 set_id 反查套装名；
        若失败则回退到直接匹配 artifact_sets.name。
        """
        try:
            from database.repository.artifact_piece_repo import ArtifactPieceRepo
            from database.repository.artifact_set_repo import ArtifactSetRepo
            from rapidfuzz import fuzz, process

            # 1. 先匹配部位单件名
            pieces = ArtifactPieceRepo.find_all_names()
            if pieces:
                piece_names = [p["name"] for p in pieces]
                result = process.extractOne(text, piece_names, scorer=fuzz.ratio)
                if result and result[1] >= 70:
                    matched_piece = next(p for p in pieces if p["name"] == result[0])
                    set_obj = ArtifactSetRepo.find_by_id(matched_piece["set_id"])
                    if set_obj:
                        return set_obj.name, result[1] / 100.0

            # 2. 回退：直接匹配套装名
            sets = ArtifactSetRepo.find_all()
            names = [s.name for s in sets]
            if names:
                result = process.extractOne(text, names, scorer=fuzz.ratio)
                if result and result[1] >= 70:
                    return result[0], result[1] / 100.0
        except Exception:  # noqa: BLE001 — 匹配失败时静默返回 None
            return None

    @classmethod
    def _match_piece_type(cls, text: str) -> dict[str, str] | None:
        """在 OCR 文本中检测圣遗物部位，返回 {type, name} 或 None。

        优先匹配 artifact_pieces.name（单件名），其次匹配 artifact_pieces.type（部位类型）。
        """
        try:
            from database.repository.artifact_piece_repo import ArtifactPieceRepo
            from rapidfuzz import fuzz, process

            pieces = ArtifactPieceRepo.find_all_names()
            if not pieces:
                # DB 为空，回退到硬编码匹配
                for pt in cls.PIECE_TYPES:
                    if pt in text:
                        return {"type": pt, "name": ""}
                return None

            # 1. 尝试匹配单件名称
            piece_names = [p["name"] for p in pieces]
            result = process.extractOne(text, piece_names, scorer=fuzz.partial_ratio)
            if result and result[1] >= 75:
                matched = next(p for p in pieces if p["name"] == result[0])
                return {"type": matched["type"], "name": matched["name"]}

            # 2. 回退：匹配部位类型
            piece_types = list({p["type"] for p in pieces})
            for pt in piece_types:
                if pt in text:
                    return {"type": pt, "name": ""}
        except Exception:  # noqa: BLE001 — 匹配失败时静默返回 None
            return None

    # ---------- 清除 ----------

    def _on_clear(self) -> None:
        self._current_result = None
        self._result_text.clear()
        if self._capture_widget:
            self._capture_widget.clear()
        log.info("已清除")