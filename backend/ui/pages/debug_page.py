"""
调试页面
========
Tab 式布局，上半部分为工具面板的 Tab 切换区，下半部分为共享预览区。
"""

from __future__ import annotations

from typing import ClassVar

from PyQt6.QtWidgets import (
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


class DebugPage(QWidget):
    """调试页面 — Tab 切换 + 底部共享预览"""

    _PREVIEW_TABS: ClassVar[set[int]] = set()

    def __init__(self, parent=None):
        super().__init__(parent)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._tabs = QTabWidget()
        self._tabs.currentChanged.connect(self._on_tab_changed)
        outer.addWidget(self._tabs)

        self._preview_container = QWidget()
        self._preview_layout = QVBoxLayout(self._preview_container)
        self._preview_layout.setContentsMargins(0, 0, 0, 0)
        self._preview_container.setVisible(False)
        outer.addWidget(self._preview_container, stretch=1)

    def add_tab(self, panel: QWidget, tab_name: str, show_preview: bool = False) -> None:
        """注册一个工具面板为独立 Tab"""
        idx = self._tabs.addTab(panel, tab_name)
        if show_preview:
            self._PREVIEW_TABS.add(idx)

    def set_preview(self, widget: QWidget) -> None:
        """设置底部共享预览组件"""
        self._preview_layout.addWidget(widget)

    def showEvent(self, event) -> None:
        """首次显示时，根据当前 Tab 同步预览区可见性"""
        super().showEvent(event)
        self._on_tab_changed(self._tabs.currentIndex())

    def _on_tab_changed(self, idx: int) -> None:
        self._preview_container.setVisible(idx in self._PREVIEW_TABS)