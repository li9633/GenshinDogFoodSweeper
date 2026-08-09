"""区域标记调试面板 — 手动输入坐标，截图并绘制矩形"""

from __future__ import annotations

import cv2
from PyQt6.QtWidgets import (
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

from backend.automation.template_manager import TemplateManager
from backend.utils.screen_capture import ScreenshotCapture


class RegionMarkerPanel(QGroupBox):
    """区域标记调试 — 基于原神窗口相对坐标绘制矩形"""

    def __init__(self, capture_widget: QWidget | None = None, parent=None):
        super().__init__("区域标记调试", parent)
        self._capture_widget = capture_widget
        self._build_ui()

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

        self._btn_clear = QPushButton("清除")
        self._btn_clear.clicked.connect(self._on_clear)
        btn_layout.addWidget(self._btn_clear)

        self._btn_copy = QPushButton("复制坐标")
        self._btn_copy.clicked.connect(self._on_copy)
        btn_layout.addWidget(self._btn_copy)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self._label_result = QLabel("输入坐标后点击「截图并标记」…")
        self._label_result.setProperty("class", "hint")
        layout.addWidget(self._label_result)

    def _on_mark(self) -> None:
        if self._capture_widget is None:
            self._label_result.setText("X 截图预览组件未初始化")
            return

        x, y = self._spin_x.value(), self._spin_y.value()
        w, h = self._spin_w.value(), self._spin_h.value()

        self._btn_mark.setEnabled(False)
        self._btn_mark.setText("截图中…")

        try:
            cap = ScreenshotCapture()
            result = cap.capture()
            result.draw_rect(
                x,
                y,
                w,
                h,
                color=(0, 255, 0),
                thickness=3,
                label=f"({x}, {y}) {w}x{h}",
            )
            pixmap = result.to_qpixmap()
            self._capture_widget.display_pixmap(pixmap, f"区域: ({x}, {y}) {w}x{h}")
            self._label_result.setText(f"✓ 已标记区域 ({x}, {y}, {w}, {h})")
        except RuntimeError as e:
            self._label_result.setText(f"X 截图失败: {e}")
        finally:
            self._btn_mark.setEnabled(True)
            self._btn_mark.setText("截图并标记")

    def _on_copy(self) -> None:
        x, y = self._spin_x.value(), self._spin_y.value()
        w, h = self._spin_w.value(), self._spin_h.value()
        QApplication.clipboard().setText(f"{x},{y},{w},{h}")
        self._label_result.setText(f"✓ 已复制坐标: {x}, {y}, {w}, {h}")

    def _on_save_template(self) -> None:
        filename = self._input_filename.text().strip()
        if not filename:
            self._label_result.setText("X 请输入文件名")
            return

        x, y = self._spin_x.value(), self._spin_y.value()
        w, h = self._spin_w.value(), self._spin_h.value()

        try:
            cap = ScreenshotCapture()
            result = cap.capture()
            roi = result.image[y:y + h, x:x + w]
            save_dir = TemplateManager.IMAGES_DIR
            save_dir.mkdir(parents=True, exist_ok=True)
            save_path = save_dir / f"{filename}.png"
            cv2.imwrite(str(save_path), cv2.cvtColor(roi, cv2.COLOR_RGB2BGR))
            TemplateManager.register(filename, f"images/{filename}.png", (x, y, w, h))
            TemplateManager.save()
            self._label_result.setText(f"✓ 已保存模板: {filename}.png ({w}x{h})，区域已写入 templates.json")
        except RuntimeError as e:
            self._label_result.setText(f"X 截图失败: {e}")

    def _on_clear(self) -> None:
        if self._capture_widget is not None:
            self._capture_widget.clear()
        self._label_result.setText("输入坐标后点击「截图并标记」…")