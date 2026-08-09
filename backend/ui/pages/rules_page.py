"""
圣遗物清理规则预设页面（占位）
==========================
自定义圣遗物清理规则，将在后续版本实现。
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class RulesPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("圣遗物清理规则预设")
        title.setProperty("class", "section-title")
        layout.addWidget(title)

        desc = QLabel("自定义圣遗物清理规则，将在后续版本实现")
        desc.setProperty("class", "hint")
        layout.addWidget(desc)