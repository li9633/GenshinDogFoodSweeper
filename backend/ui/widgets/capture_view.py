"""
截图预览组件
============
实时显示游戏窗口截图，支持区域选择。
依赖 utils.screen_capture.ScreenshotCapture。
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QPoint, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen, QPixmap, QWheelEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRubberBand,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class CapturePreviewWidget(QWidget):
    """截图预览组件 — 纯图片预览器，支持缩放"""

    region_selected = Signal(int, int, int, int)  # x, y, w, h（原始图像坐标）

    def __init__(self, parent=None):
        super().__init__(parent)
        self._zoom_factor: float = 1.0
        self._fit_to_view: bool = True
        self._current_pixmap: QPixmap | None = None
        self._selection_mode: bool = False
        self._selection_start: QPoint | None = None
        self._rubber_band: QRubberBand | None = None

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

    def draw_debug_overlay(
        self,
        rects: list[tuple[int, int, int, int, str, str]] | None = None,
        lines: list[tuple[int, int, int, int, str]] | None = None,
    ) -> None:
        """在当前预览图上绘制调试标注（矩形 + 线段 + 标签）。

        用于调试锁定图标锚点定位、搜索区域、offset 计算结果等。

        Args:
            rects: [(x, y, w, h, color_hex, label), ...]  color_hex 如 "#00FF00"
            lines: [(x1, y1, x2, y2, color_hex), ...]  线段
        """
        if self._current_pixmap is None:
            return
        pixmap = self._current_pixmap.copy()
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if rects:
            for x, y, w, h, color_hex, label in rects:
                color = QColor(color_hex)
                pen = QPen(color, 2)
                pen.setStyle(Qt.PenStyle.DashLine)
                painter.setPen(pen)
                painter.drawRect(x, y, w, h)
                if label:
                    painter.setPen(QColor(color_hex))
                    painter.drawText(x + 4, y - 4, label)

        if lines:
            for x1, y1, x2, y2, color_hex in lines:
                pen = QPen(QColor(color_hex), 1)
                pen.setStyle(Qt.PenStyle.DotLine)
                painter.setPen(pen)
                painter.drawLine(x1, y1, x2, y2)

        painter.end()
        self._current_pixmap = pixmap
        self._update_display()

    def set_selection_mode(self, enabled: bool) -> None:
        """启用/禁用鼠标拖拽选区模式"""
        self._selection_mode = enabled
        if enabled:
            self._image_label.setCursor(Qt.CursorShape.CrossCursor)
            self._image_label.setMouseTracking(True)
            self._image_label.installEventFilter(self)
        else:
            self._image_label.setCursor(Qt.CursorShape.ArrowCursor)
            self._image_label.setMouseTracking(False)
            self._image_label.removeEventFilter(self)
            self._clear_selection()

    def eventFilter(self, obj, event):
        if obj is self._image_label and self._selection_mode:
            if event.type() == QEvent.Type.MouseButtonPress:
                self._on_mouse_press(event)
                return True
            elif event.type() == QEvent.Type.MouseMove:
                self._on_mouse_move(event)
                return True
            elif event.type() == QEvent.Type.MouseButtonRelease:
                self._on_mouse_release(event)
                return True
        return super().eventFilter(obj, event)

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

        # 延迟 setWidget：全局 QSS 已应用时，立即 setWidget 会触发昂贵的样式重算
        QTimer.singleShot(0, lambda: self._scroll_area.setWidget(self._image_label))

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

    # ---------- 鼠标选区 ----------

    def _on_mouse_press(self, event: QMouseEvent) -> None:
        self._selection_start = event.pos()
        if self._rubber_band is None:
            self._rubber_band = QRubberBand(QRubberBand.Shape.Rectangle, self._image_label)
            self._rubber_band.setStyleSheet("background: rgba(0, 255, 0, 60); border: 2px solid #00FF00;")
        self._rubber_band.setGeometry(QRect(self._selection_start, self._selection_start))
        self._rubber_band.show()

    def _on_mouse_move(self, event: QMouseEvent) -> None:
        if self._selection_start and self._rubber_band:
            self._rubber_band.setGeometry(QRect(self._selection_start, event.pos()).normalized())

    def _on_mouse_release(self, event: QMouseEvent) -> None:
        if not self._selection_start or not self._rubber_band:
            return
        self._rubber_band.hide()
        rect = QRect(self._selection_start, event.pos()).normalized()
        self._selection_start = None
        if rect.width() > 5 and rect.height() > 5:
            original = self._map_to_original(rect)
            self.region_selected.emit(original.x(), original.y(), original.width(), original.height())

    def _map_to_original(self, rect: QRect) -> QRect:
        """将 QLabel 上的选区坐标映射回原始图像坐标"""
        if self._current_pixmap is None:
            return rect
        pixmap = self._image_label.pixmap()
        if pixmap is None:
            return rect
        scale_x = self._current_pixmap.width() / pixmap.width()
        scale_y = self._current_pixmap.height() / pixmap.height()
        return QRect(
            int(rect.x() * scale_x), int(rect.y() * scale_y),
            int(rect.width() * scale_x), int(rect.height() * scale_y),
        )

    def _clear_selection(self) -> None:
        if self._rubber_band:
            self._rubber_band.hide()
        self._selection_start = None

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