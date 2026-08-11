"""主题管理器 — QSS 加载与切换"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QApplication
from utils.settings_manager import settings


class ThemeManager:
    """管理明暗主题的 QSS 加载与切换"""

    _QSS_DIR = Path(__file__).parent.parent / "resources"

    def __init__(self):
        self._is_dark = settings.get_theme() == "dark"

    @property
    def is_dark(self) -> bool:
        return self._is_dark

    def apply(self, theme: str | None = None) -> None:
        """应用指定主题，未指定则使用当前主题"""
        if theme is not None:
            self._is_dark = theme == "dark"
        filename = "style.qss" if self._is_dark else "style-light.qss"
        self._load_stylesheet(filename)

    def toggle(self) -> None:
        """切换主题并持久化"""
        self._is_dark = not self._is_dark
        theme = "dark" if self._is_dark else "light"
        settings.set_theme(theme)
        self.apply()

    @staticmethod
    def _load_stylesheet(filename: str) -> None:
        qss_path = ThemeManager._QSS_DIR / filename
        if qss_path.exists():
            with open(qss_path, "r", encoding="utf-8") as f:
                qss = f.read()
            QApplication.instance().setStyleSheet(qss)