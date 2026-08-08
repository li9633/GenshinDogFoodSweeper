"""
UI 层 — PyQt6 桌面 GUI
=======================
提供系统托盘、设置窗口、截图预览等功能。
通过 API 层与后端逻辑交互，不直接调用 automation 模块。
"""

from .app import GenshinApp

__all__ = ["GenshinApp"]
