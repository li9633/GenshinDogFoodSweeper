"""
调试页面
========
包含截图预览组件，用于调试截图/识别流程。
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QFrame,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class DebugPage(QWidget):
    def __init__(self, capture_widget: QWidget | None = None, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        label = QLabel("截图预览")
        label.setProperty("class", "section-title")
        layout.addWidget(label)

        self._container = QFrame()
        self._container.setLayout(QVBoxLayout())
        self._container.layout().setContentsMargins(0, 0, 0, 0)
        self._container.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        layout.addWidget(self._container, stretch=1)

        if capture_widget is not None:
            self._container.layout().addWidget(capture_widget)
