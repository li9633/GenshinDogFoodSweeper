"""
狗粮清理器页面
==============
狗粮筛选与清理功能（占位）。
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class DogfoodPage(QWidget):
    """狗粮清理器页面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("狗粮清理器")
        title.setProperty("class", "section-title")
        layout.addWidget(title)

        desc = QLabel("狗粮筛选与清理功能将在后续版本实现")
        desc.setProperty("class", "hint")
        layout.addWidget(desc)