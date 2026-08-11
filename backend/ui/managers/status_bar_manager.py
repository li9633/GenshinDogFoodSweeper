"""状态栏管理器 — 颜色编码 + 线程安全的状态栏消息"""

from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QMainWindow, QStatusBar

# 日志级别 → 状态栏文字颜色，对齐 loguru 默认配色
_LEVEL_COLORS: dict[str, str] = {
    "DEBUG": "#3498DB",
    "INFO": "#B8B5C0",
    "SUCCESS": "#27AE60",
    "WARNING": "#F39C12",
    "ERROR": "#E74C3C",
    "CRITICAL": "#C0392B",
}


class StatusBarManager(QObject):
    """管理状态栏的颜色编码显示，支持跨线程安全调用"""

    _signal = Signal(str, str, int)

    def __init__(self, window: QMainWindow):
        super().__init__()
        self._window = window
        self._signal.connect(self._do_show)
        QTimer.singleShot(0, self._init)

    def _init(self) -> None:
        self._window.setStatusBar(QStatusBar())
        self._window.statusBar().showMessage("就绪")

    def show(self, message: str, duration: int = 0, level: str = "INFO") -> None:
        """线程安全：通过信号调度到主线程"""
        self._signal.emit(level, message, duration)

    def _do_show(self, level: str, message: str, duration: int) -> None:
        bar = self._window.statusBar()
        palette = bar.palette()
        if level.upper() == "CRITICAL":
            bar.setStyleSheet("QStatusBar { background-color: #C0392B; }")
            palette.setColor(QPalette.ColorRole.WindowText, QColor("#FFFFFF"))
        else:
            bar.setStyleSheet("")
            color = _LEVEL_COLORS.get(level.upper(), "#000000")
            palette.setColor(QPalette.ColorRole.WindowText, QColor(color))
        bar.setPalette(palette)
        bar.showMessage(message, duration)