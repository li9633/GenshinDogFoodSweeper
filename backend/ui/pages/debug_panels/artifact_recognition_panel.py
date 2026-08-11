"""圣遗物识别调试面板 — OCR + BBS 数据匹配"""

from __future__ import annotations

import copy
import time
from typing import ClassVar

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from utils.artifact_parser import ArtifactTextParser
from utils.logger import log

from backend.automation.color_sampler import sample_roi_color
from backend.automation.ocr_engine import OcrEngine
from backend.automation.recognizer import ArtifactRecognizer
from backend.utils.screen_capture import CaptureResult, ScreenshotCapture


class ArtifactRecognitionPanel(QWidget):
    """圣遗物识别调试 — 截图 → OCR → BBS 匹配"""

    PIECE_TYPES: ClassVar[set[str]] = {"生之花", "死之羽", "时之沙", "空之杯", "理之冠"}

    RARITY_COLORS: ClassVar[tuple[tuple[int, int, int], ...]] = (
        (113, 118, 138),  # 1★ #71768A
        (42, 143, 114),  # 2★ #2A8F72
        (81, 127, 203),  # 3★ #517FCB
        (161, 86, 224),  # 4★ #A156E0
        (188, 105, 50),  # 5★ #BC6932
    )

    def __init__(self, capture_widget: QWidget | None = None, parent=None):
        super().__init__(parent)
        self._capture_widget = capture_widget
        self._ocr_engine = OcrEngine()
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

        # ---- ROI 定义（可折叠，默认收起） ----
        self._roi_header = QPushButton("▸ ROI 区域定义（相对于游戏窗口）")
        self._roi_header.setCheckable(True)
        self._roi_header.setChecked(False)
        self._roi_header.setProperty("class", "collapse-header")
        self._roi_header.clicked.connect(self._on_toggle_roi_collapse)
        layout.addWidget(self._roi_header)

        self._roi_content = QWidget()
        self._roi_content.setVisible(False)
        roi_layout = QVBoxLayout()
        roi_layout.setContentsMargins(4, 4, 4, 4)
        roi_layout.setSpacing(2)
        self._roi_content.setLayout(roi_layout)

        self._chk_edit_roi = QCheckBox("编辑 ROI")
        self._chk_edit_roi.setToolTip("勾选后可修改 ROI 坐标，防止误操作")
        self._chk_edit_roi.toggled.connect(self._on_toggle_roi_edit)
        roi_layout.addWidget(self._chk_edit_roi)

        self._roi_spins: dict[str, tuple[QSpinBox, QSpinBox, QSpinBox, QSpinBox]] = {}
        defaults = [
            ("圣遗物等级", (1338, 452, 71, 44)),
            ("圣遗物星级", (1742, 159, 39, 40)),
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
                spin.setEnabled(False)
                row.addWidget(spin)
                spins.append(spin)
            self._roi_spins[name] = tuple(spins)  # type: ignore[assignment]
            row.addStretch()
            roi_layout.addLayout(row)

        layout.addWidget(self._roi_content)

        # ---- 识别结果（左右并排） ----
        result_row = QHBoxLayout()
        result_row.setSpacing(4)

        text_area_height: int = 180

        ocr_result_group = QGroupBox("识别结果（OCR 原始输出）")
        ocr_result_layout = QVBoxLayout()
        ocr_result_layout.setContentsMargins(4, 4, 4, 4)
        ocr_result_layout.setSpacing(3)
        ocr_result_group.setLayout(ocr_result_layout)

        self._ocr_result_text = QTextEdit()
        self._ocr_result_text.setReadOnly(True)
        self._ocr_result_text.setMinimumHeight(text_area_height)
        self._ocr_result_text.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._ocr_result_text.setPlaceholderText("点击「识别」查看 OCR 原始结果…")
        ocr_result_layout.addWidget(self._ocr_result_text)

        result_row.addWidget(ocr_result_group)

        structured_group = QGroupBox("格式化解析结果")
        structured_layout = QVBoxLayout()
        structured_layout.setContentsMargins(4, 4, 4, 4)
        structured_layout.setSpacing(3)
        structured_group.setLayout(structured_layout)

        self._structured_result_text = QTextEdit()
        self._structured_result_text.setReadOnly(True)
        self._structured_result_text.setMinimumHeight(text_area_height)
        self._structured_result_text.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._structured_result_text.setPlaceholderText("结构化解析结果将显示在此…")
        structured_layout.addWidget(self._structured_result_text)

        result_row.addWidget(structured_group)

        layout.addLayout(result_row)

        # ---- 操作按钮 ----
        btn_row = QHBoxLayout()
        btn_row.setSpacing(3)
        self._btn_capture = QPushButton("截图并识别")
        self._btn_capture.setProperty("class", "primary")
        self._btn_capture.clicked.connect(self._on_capture_and_recognize)
        btn_row.addWidget(self._btn_capture)
        self._btn_clear = QPushButton("清除")
        self._btn_clear.clicked.connect(self._on_clear)
        btn_row.addWidget(self._btn_clear)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        scroll.setWidget(content)
        outer_layout.addWidget(scroll)

    # ---------- 截图并识别 ----------

    def _on_capture_and_recognize(self) -> None:
        self._btn_capture.setEnabled(False)
        self._btn_capture.setText("截图中…")
        try:
            cap = ScreenshotCapture()
            self._current_result = cap.capture()
            if self._capture_widget:
                self._capture_widget.display_pixmap(
                    self._current_result.to_qpixmap(), "截图完成"
                )
        except RuntimeError as e:
            log.error(f"截图失败: {e}")
            self._btn_capture.setEnabled(True)
            self._btn_capture.setText("截图并识别")
            return

        self._btn_capture.setText("识别中…")
        self._do_recognize()
        self._btn_capture.setEnabled(True)
        self._btn_capture.setText("截图并识别")

    # ---------- 识别 ----------

    def _do_recognize(self) -> None:
        try:
            t0 = time.perf_counter()
            ocr = self._ocr_engine.get()
            lines: list[str] = []

            db_empty = ArtifactRecognizer.is_db_empty()
            if db_empty:
                QMessageBox.warning(
                    self,
                    "本地圣遗物模板为空",
                    "数据库中暂无圣遗物套装数据，将仅显示 OCR 识别结果，不进行匹配。\n\n"
                    "请前往[设置]页面，点击「圣遗物同步」拉取最新圣遗物数据。",
                )
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

            for name, (sx, sy, sw, sh) in self._roi_spins.items():
                x, y, w, h = sx.value(), sy.value(), sw.value(), sh.value()
                roi = self._current_result.image[y : y + h, x : x + w]
                if roi.size == 0:
                    lines.append(f"[{name}] 区域无效")
                    continue

                roi_path = ArtifactRecognizer.save_roi_temp(roi, name)

                ocr_result = ocr.ocr(roi)
                texts: list[str] = []
                dt_count = 0
                if ocr_result and ocr_result[0]:
                    result = ocr_result[0]
                    if isinstance(result, dict):
                        texts = [
                            t for t in result.get("rec_texts", []) if t and t.strip()
                        ]
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
                            if (
                                isinstance(line_info, (list, tuple))
                                and len(line_info) >= 2
                            ):
                                rec = line_info[1]
                                text = (
                                    rec[0]
                                    if isinstance(rec, (list, tuple))
                                    else str(rec)
                                )
                            else:
                                text = str(line_info)
                            if text.strip():
                                texts.append(text.strip())
                    else:
                        log.warning(f"[{name}] 未知 OCR 结果类型: {type(result)}")

                combined = " | ".join(texts) if texts else "(无文本)"
                ocr_texts[name] = texts
                lines.append(f"[{name}] OCR: {combined}")
                if texts:
                    lines.append(
                        f"  → 检测到 {dt_count} 个文本块，识别出 {len(texts)} 个"
                    )
                elif dt_count > 0:
                    lines.append(
                        f"  → 检测到 {dt_count} 个文本块，但识别失败（可能是字体/颜色问题）"
                    )
                else:
                    lines.append(
                        f"  → 未检测到任何文本（坐标可能不对，请检查 {roi_path.name}）"
                    )

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
                            f"[匹配套装] OCR='{texts[0]}' → set_name='{match[0]}' set_id={match[1]} "
                            f"piece_type={match[2]} piece_name={match[3]} score={match[4]:.3f}"
                        )
                    else:
                        lines.append("  → 未匹配到套装")
                elif name == "部位+主词条" and texts:
                    if piece_from_set_match:
                        pass
                    else:
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

            # --- 星级识别：颜色采样 ---
            if not db_empty and matched_set_id is not None:
                from database.repository.artifact_set_repo import ArtifactSetRepo

                set_obj = ArtifactSetRepo.find_by_id(matched_set_id)
                if set_obj:
                    matched_set_rarities = set_obj.rarity
            if "圣遗物星级" in self._roi_spins:
                sx, sy, sw, sh = self._roi_spins["圣遗物星级"]
                x, y, w, h = sx.value(), sy.value(), sw.value(), sh.value()
                roi = self._current_result.image[y : y + h, x : x + w]
                if roi.size > 0:
                    rgb = sample_roi_color(self._current_result.image, x, y, w, h)
                    detected = ArtifactRecognizer.classify_rarity(rgb)
                    if detected is not None:
                        if matched_set_rarities:
                            detected_str = str(detected)
                            if detected_str in matched_set_rarities:
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

            # --- 锁定状态 ---
            lock_status: bool | None = None
            if self._current_result is not None:
                lock_status = ArtifactRecognizer.match_lock_status(
                    self._current_result.image
                )
                if lock_status is True:
                    lines.append("[圣遗物锁定状态] 已锁定")
                elif lock_status is False:
                    lines.append("[圣遗物锁定状态] 未锁定")
                else:
                    lines.append("[圣遗物锁定状态] 未能识别（模板匹配失败）")

            # --- 结构化解析 ---
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

            ocr_lines = lines
            structured_lines: list[str] = []

            structured_lines.append("【结构化解析结果】")
            structured_lines.append(f"  套装: {artifact.set_name or '未识别'}")
            if artifact.set_effects:
                for key in ("1pc", "2pc", "4pc"):
                    if key in artifact.set_effects:
                        label = {"1pc": "1件套", "2pc": "2件套", "4pc": "4件套"}[key]
                        structured_lines.append(
                            f"    {label}: {artifact.set_effects[key]}"
                        )
            if artifact.level is not None:
                structured_lines.append(f"  等级: +{artifact.level}")
            if artifact.is_locked is not None:
                structured_lines.append(
                    f"  锁定: {'是' if artifact.is_locked else '否'}"
                )
            if artifact.piece_type:
                detail = artifact.piece_type
                if artifact.piece_name:
                    detail += f" ({artifact.piece_name})"
                structured_lines.append(f"  部位: {detail}")
            if matched_rarity is not None:
                structured_lines.append(f"  星级: {matched_rarity}★")
            if artifact.main_stat:
                ms = artifact.main_stat
                pct = "%" if ms.is_percentage else ""
                structured_lines.append(f"  主词条: {ms.name} +{ms.value}{pct}")
            if artifact.sub_stats:
                structured_lines.append("  副词条:")
                for ss in artifact.sub_stats:
                    pct = "%" if ss.is_percentage else ""
                    lock = " (待激活)" if ss.is_locked else ""
                    structured_lines.append(f"    • {ss.name} +{ss.value}{pct}{lock}")
            else:
                structured_lines.append("  副词条: 未解析到")

            elapsed = (time.perf_counter() - t0) * 1000
            ocr_lines.append(f"\n总耗时: {elapsed:.0f}ms")
            self._ocr_result_text.setText("\n".join(ocr_lines))
            self._structured_result_text.setText("\n".join(structured_lines))

            if self._capture_widget:
                self._capture_widget.display_pixmap(
                    display.to_qpixmap(), f"识别完成 ({elapsed:.0f}ms)"
                )

            log.info(f"识别完成 ({elapsed:.0f}ms)")

        except Exception as e:  # noqa: BLE001 — 顶层兜底，确保 UI 不会崩溃
            log.error(f"识别失败: {e}")
            self._ocr_result_text.setText(f"错误: {e}")

    # ---------- ROI 折叠 ----------

    def _on_toggle_roi_collapse(self, checked: bool) -> None:
        self._roi_content.setVisible(checked)
        self._roi_header.setText(
            "▾ ROI 区域定义（相对于游戏窗口）"
            if checked
            else "▸ ROI 区域定义（相对于游戏窗口）"
        )

    def _on_toggle_roi_edit(self, checked: bool) -> None:
        for spins in self._roi_spins.values():
            for spin in spins:
                spin.setEnabled(checked)

    # ---------- 清除 ----------

    def _on_clear(self) -> None:
        self._ocr_result_text.clear()
        self._structured_result_text.clear()
        if self._capture_widget is not None:
            self._capture_widget.clear()
        self._current_result = None
        log.info("已清除识别结果")