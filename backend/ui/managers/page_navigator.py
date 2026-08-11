"""
页面导航管理器
=============
管理页面懒加载、QStackedWidget 切换和 Sidebar 高亮同步。
MainWindow 只需定义页面工厂并注册，导航逻辑完全由本模块负责。
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QStackedWidget, QWidget

from backend.ui.widgets.sidebar import Sidebar


class PageNavigator:
    """页面导航管理器 — 页面注册、懒加载、切换"""

    def __init__(self, stack: QStackedWidget, sidebar: Sidebar):
        self._stack = stack
        self._sidebar = sidebar
        self._pages: dict[str, QWidget] = {}
        self._factories: dict[str, Callable[[], QWidget]] = {}

    # ---------- 公开 API ----------

    def register(self, key: str, factory: Callable[[], QWidget]) -> None:
        """注册页面工厂函数（首次访问时懒加载）"""
        self._factories[key] = factory

    def switch_to(self, key: str) -> None:
        """切换到指定页面，首次访问时自动懒加载并同步 Sidebar 高亮"""
        if key not in self._pages:
            factory = self._factories.get(key)
            if factory is None:
                return
            page = factory()
            self._pages[key] = page

            self._stack.setUpdatesEnabled(False)
            self._stack.addWidget(page)
            self._stack.setUpdatesEnabled(True)

        self._stack.setCurrentWidget(self._pages[key])
        self._sidebar.set_active(key)

    def get_page(self, key: str) -> QWidget | None:
        """获取已加载的页面实例（未加载返回 None）"""
        return self._pages.get(key)