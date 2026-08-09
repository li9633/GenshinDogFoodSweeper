"""
清理器页面
==========
狗粮筛选与清理功能（占位），包含扫描/停止控制按钮。
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class CleanerPage(QWidget):
    """清理器页面"""

    scan_requested = pyqtSignal()
    stop_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("清理器")
        title.setProperty("class", "section-title")
        layout.addWidget(title)

        desc = QLabel("狗粮筛选与清理功能将在后续版本实现")
        desc.setProperty("class", "hint")
        layout.addWidget(desc)

        # 扫描控制按钮
        btn_row = QHBoxLayout()
        btn_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._btn_scan = QPushButton("开始扫描")
        self._btn_scan.setProperty("class", "primary")
        self._btn_scan.clicked.connect(self._on_scan)
        btn_row.addWidget(self._btn_scan)

        self._btn_stop = QPushButton("停止")
        self._btn_stop.setProperty("class", "danger")
        self._btn_stop.setEnabled(False)
        self._btn_stop.clicked.connect(self.stop_requested.emit)
        btn_row.addWidget(self._btn_stop)

        layout.addLayout(btn_row)

    def set_scanning(self, active: bool):
        """更新按钮状态"""
        self._btn_scan.setEnabled(not active)
        self._btn_stop.setEnabled(active)

    def _on_scan(self):
        self.scan_requested.emit()