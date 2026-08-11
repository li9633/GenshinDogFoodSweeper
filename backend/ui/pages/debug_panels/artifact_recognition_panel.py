"""圣遗物识别调试面板 — View 层（仅 UI 渲染 + 简单交互）"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
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
from utils.logger import log

from backend.ui.presenters.artifact_recognition_presenter import (
    ArtifactRecognitionPresenter,
)


class ArtifactRecognitionPanel(QWidget):
    """圣遗物识别调试 — View 层"""

    def __init__(self, capture_widget: QWidget | None = None, parent=None):
        super().__init__(parent)
        self._capture_widget = capture_widget
        self._presenter = ArtifactRecognitionPresenter()
        self._build_ui()
        self._connect_ocr_worker()

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

        # ROI 折叠区
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

        # 识别结果（左右并排）
        result_row = QHBoxLayout()
        result_row.setSpacing(4)
        text_area_height = 180

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

        # 操作按钮
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

    # ---------- 交互 ----------

    def _on_capture_and_recognize(self) -> None:
        self._set_btn_loading(True)
        QApplication.processEvents()

        roi_values = {
            name: (sx.value(), sy.value(), sw.value(), sh.value())
            for name, (sx, sy, sw, sh) in self._roi_spins.items()
        }

        try:
            capture = self._presenter.capture()
            if self._capture_widget:
                self._capture_widget.display_pixmap(capture.to_qpixmap(), "截图完成")

            image = capture.image.copy()

            from backend.automation.ocr_worker import OcrWorker

            task_fn = ArtifactRecognitionPresenter.create_recognition_task(
                image, roi_values#$
            )
            worker = OcrWorker.instance()
            worker.submit(task_fn, callback_data=capture)
        except Exception:  # noqa: BLE001
            import traceback

            self._on_recognize_error(traceback.format_exc())

    def _connect_ocr_worker(self) -> None:
        """连接 OcrWorker 的信号回调"""
        from backend.automation.ocr_worker import OcrWorker

        worker = OcrWorker.instance()
        worker.task_done.connect(self._on_ocr_task_done)
        worker.task_error.connect(self._on_ocr_task_error)

    def _on_ocr_task_done(self, result: dict, callback_data: object) -> None:
        """OCR Worker 返回结果（在后台线程完成，通过信号回到主线程）"""
        data = result

        if data["db_empty"]:
            QMessageBox.warning(
                self,
                "本地圣遗物模板为空",
                "数据库中暂无圣遗物套装数据，将仅显示 OCR 识别结果，不进行匹配。\n\n"
                "请前往[设置]页面，点击「圣遗物同步」拉取最新圣遗物数据。",
            )

        self._ocr_result_text.setText("\n".join(data["ocr_lines"]))
        self._structured_result_text.setText("\n".join(data["structured_lines"]))

        if self._capture_widget:
            self._capture_widget.display_pixmap(
                data["display_result"].to_qpixmap(),
                f"识别完成 ({data['elapsed_ms']:.0f}ms)",
            )
        log.info(f"识别完成 ({data['elapsed_ms']:.0f}ms)")
        self._set_btn_loading(False)

    def _on_ocr_task_error(self, error: str, _callback_data: object) -> None:
        """OCR Worker 返回错误"""
        self._on_recognize_error(error)

    def _on_recognize_error(self, error: str) -> None:
        log.error(f"识别失败: {error}")
        self._ocr_result_text.setText(f"错误: {error}")
        self._set_btn_loading(False)

    def _set_btn_loading(self, loading: bool) -> None:
        self._btn_capture.setEnabled(not loading)
        self._btn_capture.setText("识别中…" if loading else "截图并识别")

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

    def _on_clear(self) -> None:
        self._ocr_result_text.clear()
        self._structured_result_text.clear()
        if self._capture_widget is not None:
            self._capture_widget.clear()
        log.info("已清除识别结果")