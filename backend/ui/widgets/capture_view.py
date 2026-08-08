"""
截图预览组件
============
实时显示游戏窗口截图，支持区域选择。
依赖 utils.screen_capture.ScreenshotCapture。
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class CapturePreviewWidget(QWidget):
    """截图预览组件 — 实时显示窗口截图"""

    capture_started = pyqtSignal()
    capture_stopped = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._active = False
        self._capture = None  # 延迟初始化 ScreenshotCapture

        self._build_ui()

    # ---------- 公开方法 ----------

    def start_preview(self, interval_ms: int = 500):
        """开始定时刷新预览"""
        if self._capture is None:
            from backend.utils.screen_capture import ScreenshotCapture

            self._capture = ScreenshotCapture()
        self._active = True
        self._timer.start(interval_ms)
        self._btn_toggle.setText("停止预览")
        self.capture_started.emit()

    def stop_preview(self):
        """停止预览"""
        self._active = False
        self._timer.stop()
        self._btn_toggle.setText("开始预览")
        self.capture_stopped.emit()

    def take_snapshot(self) -> QPixmap | None:
        """单次截图，返回 QPixmap"""
        if self._capture is None:
            from backend.utils.screen_capture import ScreenshotCapture

            self._capture = ScreenshotCapture()
        try:
            result = self._capture.capture()
            return result.to_qpixmap()
        except (RuntimeError, ImportError):
            return None

    # ---------- 内部 ----------

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 控制栏
        ctrl_layout = QHBoxLayout()

        self._btn_toggle = QPushButton("开始预览")
        self._btn_toggle.clicked.connect(self._toggle)
        ctrl_layout.addWidget(self._btn_toggle)

        self._btn_snapshot = QPushButton("单次截图")
        self._btn_snapshot.clicked.connect(self._on_snapshot)
        ctrl_layout.addWidget(self._btn_snapshot)

        ctrl_layout.addStretch()

        self._label_info = QLabel("等待截图…")
        ctrl_layout.addWidget(self._label_info)

        layout.addLayout(ctrl_layout)

        # 预览区域
        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_label.setMinimumHeight(300)
        self._image_label.setStyleSheet(
            "QLabel { background-color: #1e1e1e; border: 1px solid #3a3a3a; }"
        )
        self._image_label.setText("未开始预览\n点击「开始预览」查看游戏画面")
        layout.addWidget(self._image_label)

    def _toggle(self):
        if self._active:
            self.stop_preview()
        else:
            self.start_preview()

    def _refresh(self):
        """定时刷新预览画面"""
        try:
            result = self._capture.capture()
            pixmap = result.to_qpixmap()
            scaled = pixmap.scaled(
                self._image_label.width(),
                self._image_label.height(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._image_label.setPixmap(scaled)
            self._label_info.setText(
                f"{result.width}x{result.height} | {result.elapsed_ms:.0f}ms"
            )
        except (RuntimeError, ImportError) as e:
            self._label_info.setText(f"截图失败: {e}")

    def _on_snapshot(self):
        """单次截图"""
        pixmap = self.take_snapshot()
        if pixmap:
            scaled = pixmap.scaled(
                self._image_label.width(),
                self._image_label.height(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._image_label.setPixmap(scaled)
            self._label_info.setText(f"{pixmap.width()}x{pixmap.height()} (单次)")