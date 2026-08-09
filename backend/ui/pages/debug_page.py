"""
调试页面
========
纯布局容器，子面板通过 add_panel() 注册。
不包含任何业务逻辑，所有调试功能由独立的 debug_panels 子组件提供。
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QFrame,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class DebugPage(QWidget):
    """调试页面 — 纯布局容器，子面板通过 add_panel() 注册"""

    def __init__(self, parent=None):
        super().__init__(parent)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._panel_container = QWidget()
        self._panel_layout = QVBoxLayout(self._panel_container)
        self._panel_layout.setContentsMargins(0, 0, 0, 0)

        scroll.setWidget(self._panel_container)
        outer_layout.addWidget(scroll)

    def add_panel(
        self, panel: QWidget, stretch: int = 0, title: str | None = None
    ) -> None:
        """
        注册一个调试面板到布局中。

        参数:
            panel: 面板组件（如 QGroupBox、CapturePreviewWidget）
            stretch: 拉伸因子，0=固定高度，1=自动扩展
            title: 可选标题，会以 section-title 样式渲染在面板上方
        """
        if title:
            label = QLabel(title)
            label.setProperty("class", "section-title")
            self._panel_layout.addWidget(label)
        self._panel_layout.addWidget(panel, stretch=stretch)