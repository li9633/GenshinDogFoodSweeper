"""
应用主入口
==========
极薄封装：创建 QApplication → MainWindow → 进入事件循环。
所有业务逻辑由 MainWindow 内部协调。
"""

from __future__ import annotations

from PyQt6.QtCore import QObject
from PyQt6.QtWidgets import QApplication

from .main_window import MainWindow


class GenshinApp(QObject):
    """应用入口 — 仅负责创建 MainWindow 并运行事件循环"""

    def __init__(self, qapp: QApplication):
        super().__init__()
        self._qapp = qapp
        self._main_window = MainWindow()
        self._main_window.app_exit_requested.connect(self._qapp.quit)
        self._main_window.show()

    def run(self):
        """进入事件循环"""
        self._qapp.exec()