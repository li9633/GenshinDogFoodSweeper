"""
圣遗物锁定器页面
================
圣遗物锁定功能（占位）。
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class LockerPage(QWidget):
    """圣遗物锁定器页面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("圣遗物锁定器")
        title.setProperty("class", "section-title")
        layout.addWidget(title)

        desc = QLabel("圣遗物锁定功能将在后续版本实现")
        desc.setProperty("class", "hint")
        layout.addWidget(desc)