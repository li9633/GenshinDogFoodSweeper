"""区域标记调试面板 — View 层（仅 UI 渲染 + 简单交互）"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QApplication,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from utils.logger import log

from backend.ui.presenters.async_runner import run_async
from backend.ui.presenters.region_marker_presenter import RegionMarkerPresenter


class RegionMarkerPanel(QGroupBox):
    """区域标记调试 — View 层"""

    def __init__(self, capture_widget: QWidget | None = None, parent=None):
        super().__init__("区域标记调试", parent)
        self._capture_widget = capture_widget
        self._presenter = RegionMarkerPresenter()
        self._build_ui()
        self._connect_selection()

    def _build_ui(self) -> None:
        layout = QVBoxLayout()
        self.setLayout(layout)

        coord_layout = QHBoxLayout()
        coord_layout.addWidget(QLabel("X:"))
        self._spin_x = QSpinBox()
        self._spin_x.setRange(0, 9999)
        coord_layout.addWidget(self._spin_x)
        coord_layout.addWidget(QLabel("Y:"))
        self._spin_y = QSpinBox()
        self._spin_y.setRange(0, 9999)
        coord_layout.addWidget(self._spin_y)
        coord_layout.addWidget(QLabel("宽:"))
        self._spin_w = QSpinBox()
        self._spin_w.setRange(1, 9999)
        self._spin_w.setValue(100)
        coord_layout.addWidget(self._spin_w)
        coord_layout.addWidget(QLabel("高:"))
        self._spin_h = QSpinBox()
        self._spin_h.setRange(1, 9999)
        self._spin_h.setValue(100)
        coord_layout.addWidget(self._spin_h)
        layout.addLayout(coord_layout)

        save_layout = QHBoxLayout()
        save_layout.addWidget(QLabel("文件名:"))
        self._input_filename = QLineEdit()
        self._input_filename.setPlaceholderText("输入模板名称，如 圣遗物文本")
        save_layout.addWidget(self._input_filename, stretch=1)
        self._btn_save = QPushButton("保存为模板")
        self._btn_save.clicked.connect(self._on_save_template)
        save_layout.addWidget(self._btn_save)
        layout.addLayout(save_layout)

        btn_layout = QHBoxLayout()
        self._btn_mark = QPushButton("截图并标记")
        self._btn_mark.setProperty("class", "primary")
        self._btn_mark.clicked.connect(self._on_mark)
        btn_layout.addWidget(self._btn_mark)
        self._btn_select = QPushButton("选区模式")
        self._btn_select.setCheckable(True)
        self._btn_select.toggled.connect(self._on_toggle_selection)
        btn_layout.addWidget(self._btn_select)
        self._btn_copy = QPushButton("复制坐标")
        self._btn_copy.clicked.connect(self._on_copy)
        btn_layout.addWidget(self._btn_copy)
        self._btn_clear = QPushButton("清除")
        self._btn_clear.clicked.connect(self._on_clear)
        btn_layout.addWidget(self._btn_clear)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        color_layout = QHBoxLayout()
        self._btn_color = QPushButton("提取颜色")
        self._btn_color.setProperty("class", "primary")
        self._btn_color.clicked.connect(self._on_extract_color)
        color_layout.addWidget(self._btn_color)
        self._color_swatch = QLabel()
        self._color_swatch.setFixedSize(24, 24)
        self._color_swatch.setStyleSheet("border: 1px solid #555; border-radius: 2px;")
        color_layout.addWidget(self._color_swatch)
        self._color_info = QLabel("点击按钮提取区域颜色")
        color_layout.addWidget(self._color_info, stretch=1)
        layout.addLayout(color_layout)

    # ---------- 交互 ----------

    def _coords(self) -> tuple[int, int, int, int]:
        return (
            self._spin_x.value(),
            self._spin_y.value(),
            self._spin_w.value(),
            self._spin_h.value(),
        )

    def _on_mark(self) -> None:
        if self._capture_widget is None:
            log.error("截图预览组件未初始化")
            return

        x, y, w, h = self._coords()
        self._btn_mark.setEnabled(False)
        self._btn_mark.setText("截图中…")
        QApplication.processEvents()

        run_async(
            lambda: self._presenter.mark_region(
                self._presenter.capture(), x, y, w, h
            ),
            on_result=lambda r: self._on_mark_result(r, x, y, w, h),
            on_error=self._on_mark_error,
            parent=self,
        )

    def _on_mark_result(self, result, x, y, w, h) -> None:
        self._capture_widget.display_pixmap(
            result.to_qpixmap(), f"区域: ({x}, {y}) {w}x{h}"
        )
        log.debug(f"已标记区域 ({x}, {y}, {w}, {h})")
        self._btn_mark.setEnabled(True)
        self._btn_mark.setText("截图并标记")

    def _on_mark_error(self, error: str) -> None:
        log.error(f"截图失败: {error}")
        self._btn_mark.setEnabled(True)
        self._btn_mark.setText("截图并标记")

    def _on_copy(self) -> None:
        x, y, w, h = self._coords()
        QApplication.clipboard().setText(f"{x},{y},{w},{h}")
        log.debug(f"已复制坐标: {x}, {y}, {w}, {h}")

    def _on_save_template(self) -> None:
        filename = self._input_filename.text().strip()
        if not filename:
            log.warning("请输入文件名")
            return
        x, y, w, h = self._coords()
        run_async(
            lambda: self._presenter.save_template(
                self._presenter.capture(), filename, x, y, w, h
            ),
            on_error=lambda e: log.error(f"截图失败: {e}"),
            parent=self,
        )

    def _on_clear(self) -> None:
        if self._capture_widget is not None:
            self._capture_widget.clear()
        log.debug("已清除")

    def _on_extract_color(self) -> None:
        x, y, w, h = self._coords()
        self._btn_color.setEnabled(False)
        self._btn_color.setText("提取中…")
        QApplication.processEvents()

        run_async(
            lambda: self._presenter.extract_color(
                self._presenter.capture(), x, y, w, h
            ),
            on_result=self._on_color_result,
            on_error=self._on_color_error,
            parent=self,
        )

    def _on_color_result(self, c: dict) -> None:
        self._color_swatch.setStyleSheet(
            f"background-color: rgb({c['r']},{c['g']},{c['b']}); "
            f"border: 1px solid #555; border-radius: 2px;"
        )
        self._color_info.setText(
            f"RGB({c['r']}, {c['g']}, {c['b']})  "
            f"HSV({c['h_hsv']}°, {c['s_hsv'] / 255:.0%}, {c['v_hsv'] / 255:.0%})"
        )
        log.debug(
            f"颜色提取: RGB({c['r']},{c['g']},{c['b']}) "
            f"HSV({c['h_hsv']},{c['s_hsv']},{c['v_hsv']})"
        )
        self._btn_color.setEnabled(True)
        self._btn_color.setText("提取颜色")

    def _on_color_error(self, error: str) -> None:
        log.error(f"截图失败: {error}")
        self._btn_color.setEnabled(True)
        self._btn_color.setText("提取颜色")

    # ---------- 选区模式 ----------

    def _connect_selection(self) -> None:
        if self._capture_widget is not None and hasattr(
            self._capture_widget, "region_selected"
        ):
            self._capture_widget.region_selected.connect(self._on_region_selected)

    def _on_toggle_selection(self, checked: bool) -> None:
        if self._capture_widget is not None and hasattr(
            self._capture_widget, "set_selection_mode"
        ):
            self._capture_widget.set_selection_mode(checked)
        self._btn_select.setText("选区中…" if checked else "选区模式")
        if checked:
            log.debug("进入选区模式，在截图上拖拽鼠标选择区域")

    def _on_region_selected(self, x: int, y: int, w: int, h: int) -> None:
        self._spin_x.setValue(x)
        self._spin_y.setValue(y)
        self._spin_w.setValue(w)
        self._spin_h.setValue(h)
        if self._capture_widget is not None and hasattr(
            self._capture_widget, "set_selection_mode"
        ):
            self._capture_widget.set_selection_mode(False)
        self._btn_select.setChecked(False)
        self._btn_select.setText("选区模式")
        log.debug(f"已选区: ({x}, {y}, {w}x{h})")