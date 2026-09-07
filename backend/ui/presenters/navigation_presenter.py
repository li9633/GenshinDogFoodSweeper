"""
导航路由 Presenter
==================
提供类似 Vue Router 的统一导航功能。各模块在启动时注册自己的路由，
通过 navigate(path) 即可跳转到任意页面/子Tab，无需硬编码索引。
"""

from __future__ import annotations

from typing import ClassVar

from PySide6.QtCore import QObject, Signal


class _RouteEntry:
    """路由条目"""

    __slots__ = ("page", "tab")

    def __init__(self, page: str, tab: str = "") -> None:
        self.page = page
        self.tab = tab


class NavigationPresenter(QObject):
    """导航路由中心 — 单例，注册为 QML context property"""

    _instance: ClassVar[NavigationPresenter | None] = None

    _routes: ClassVar[dict[str, _RouteEntry]] = {}

    # 通知 QML 执行页面跳转: page=页面key, tab=子Tab key（可选）
    navigateRequested = Signal(str, str)

    def __init__(self, parent: QObject | None = None) -> None:
        if NavigationPresenter._instance is not None:
            raise RuntimeError("NavigationPresenter 是单例，请勿重复创建")
        super().__init__(parent)
        NavigationPresenter._instance = self

    # ========== 公开 API ==========

    @classmethod
    def register(cls, path: str, page: str, tab: str = "") -> None:
        """注册路由。

        Args:
            path: 路由路径，如 "settings/sync"、"dogfood"
            page: 页面 key，对应 MainWindow.getPageComponent(key)
            tab: 子Tab key（可选），对应 SettingsPage.goToTab(key)
        """
        cls._routes[path] = _RouteEntry(page, tab)

    @classmethod
    def navigate(cls, path: str) -> None:
        """导航到指定路径。

        若路径未注册或实例未就绪，静默忽略。
        """
        entry = cls._routes.get(path)
        if entry is None or cls._instance is None:
            return
        cls._instance.navigateRequested.emit(entry.page, entry.tab)