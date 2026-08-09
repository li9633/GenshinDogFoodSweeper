"""
截图预览组件
============
实时显示游戏窗口截图，支持区域选择。
依赖 utils.screen_capture.ScreenshotCapture。
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QWheelEvent
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class CapturePreviewWidget(QWidget):
    """截图预览组件 — 纯图片预览器，支持缩放"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._zoom_factor: float = 1.0
        self._fit_to_view: bool = True
        self._current_pixmap: QPixmap | None = None

        self._build_ui()

    # ---------- 公开方法 ----------

    def display_pixmap(self, pixmap: QPixmap, info_text: str = "") -> None:
        """显示 pixmap（如带标注的截图）"""
        self._current_pixmap = pixmap
        self._update_display()
        if info_text:
            self._label_info.setText(info_text)

    def clear(self) -> None:
        """清除当前显示的图片"""
        self._current_pixmap = None
        self._image_label.clear()
        self._label_info.setText("等待截图…")

    # ---------- 内部 ----------

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        ctrl_layout = QHBoxLayout()

        ctrl_layout.addStretch()

        self._btn_zoom_out = QPushButton("-")
        self._btn_zoom_out.setFixedWidth(28)
        self._btn_zoom_out.setStyleSheet("padding-left: 2px; padding-right: 2px;")
        self._btn_zoom_out.clicked.connect(self._zoom_out)
        ctrl_layout.addWidget(self._btn_zoom_out)

        self._label_zoom = QLabel("适应")
        self._label_zoom.setFixedWidth(40)
        self._label_zoom.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ctrl_layout.addWidget(self._label_zoom)

        self._btn_zoom_in = QPushButton("+")
        self._btn_zoom_in.setFixedWidth(28)
        self._btn_zoom_in.setStyleSheet("padding-left: 2px; padding-right: 2px;")
        self._btn_zoom_in.clicked.connect(self._zoom_in)
        ctrl_layout.addWidget(self._btn_zoom_in)

        self._btn_zoom_fit = QPushButton("适应")
        self._btn_zoom_fit.setFixedWidth(44)
        self._btn_zoom_fit.setStyleSheet("padding-left: 2px; padding-right: 2px;")
        self._btn_zoom_fit.clicked.connect(self._zoom_fit)
        ctrl_layout.addWidget(self._btn_zoom_fit)

        self._label_info = QLabel("等待截图…")
        self._label_info.setProperty("class", "hint")
        ctrl_layout.addWidget(self._label_info)

        layout.addLayout(ctrl_layout)

        # 预览区域（可滚动）
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(False)
        self._scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._scroll_area.setStyleSheet(
            "QScrollArea {"
            "  background-color: #1A1B2E;"
            "  border: 1px solid #3A3D5C;"
            "  border-radius: 8px;"
            "}"
        )
        self._scroll_area.setMinimumHeight(300)

        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_label.setStyleSheet(
            "QLabel {"
            "  background-color: transparent;"
            "  border: none;"
            "  color: #6B6E8A;"
            "  font-size: 14px;"
            "}"
        )
        self._image_label.setText("未开始预览\n点击「开始预览」查看游戏画面")
        self._scroll_area.setWidget(self._image_label)
        layout.addWidget(self._scroll_area)

    # ---------- 缩放 ----------

    def _zoom_in(self) -> None:
        self._fit_to_view = False
        self._zoom_factor = min(self._zoom_factor + 0.25, 5.0)
        self._update_display()

    def _zoom_out(self) -> None:
        self._fit_to_view = False
        self._zoom_factor = max(self._zoom_factor - 0.25, 0.25)
        self._update_display()

    def _zoom_fit(self) -> None:
        self._fit_to_view = True
        self._update_display()

    def _update_display(self) -> None:
        if self._current_pixmap is None:
            return
        if self._fit_to_view:
            size = self._scroll_area.viewport().size()
            scaled = self._current_pixmap.scaled(
                size, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._label_zoom.setText("适应")
        else:
            new_w = int(self._current_pixmap.width() * self._zoom_factor)
            new_h = int(self._current_pixmap.height() * self._zoom_factor)
            scaled = self._current_pixmap.scaled(
                new_w, new_h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._label_zoom.setText(f"{int(self._zoom_factor * 100)}%")
        self._image_label.setPixmap(scaled)
        self._image_label.resize(scaled.size())

    def wheelEvent(self, event: QWheelEvent) -> None:
        if self._current_pixmap is not None and (
            event.modifiers() & Qt.KeyboardModifier.ControlModifier
        ):
            delta = event.angleDelta().y()
            if delta > 0:
                self._zoom_in()
            elif delta < 0:
                self._zoom_out()
        else:
            super().wheelEvent(event)