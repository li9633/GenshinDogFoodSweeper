"""TitleBar Presenter — 自绘标题栏的业务逻辑层"""

from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot
from PySide6.QtGui import QGuiApplication, QWindow

from common.constants import APP_NAME_CN


class TitleBarPresenter(QObject):
    """标题栏 Presenter

    职责：
    - 计算窗口标题（含调试模式标识、版本号等）
    - 最大化/还原切换
    - 最小化到托盘
    """

    titleChanged = Signal()
    maximizedChanged = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._title = ""
        self._maximized = False
        self._window: QWindow | None = None
        self._refresh_title()

    def _refresh_title(self) -> None:
        from common.env_manager import EnvManager
        from common.version_manager import AppVersion

        base = APP_NAME_CN
        if EnvManager.is_debug():
            self._title = f"{base}（调试模式）"
        else:
            self._title = f"{base} {AppVersion.display()}"
        self.titleChanged.emit()

    def _get_window(self) -> QWindow | None:
        """延迟获取主窗口引用，首次获取时连接 visibilityChanged 信号"""
        if self._window is not None:
            return self._window
        app = QGuiApplication.instance()
        if app is None:
            return None
        for w in app.topLevelWindows():
            if w.isVisible():
                self._window = w
                w.visibilityChanged.connect(self._on_visibility_changed)
                self._maximized = w.visibility() == QWindow.Maximized
                return w
        return None

    def _on_visibility_changed(self, visibility: QWindow.Visibility) -> None:
        maximized = visibility == QWindow.Maximized
        if maximized != self._maximized:
            self._maximized = maximized
            self.maximizedChanged.emit()

    @Slot()
    def toggleMaximize(self) -> None:
        """切换最大化/还原"""
        window = self._get_window()
        if window is None:
            return
        if window.visibility() == QWindow.Maximized:
            window.showNormal()
        else:
            window.showMaximized()

    @Slot()
    def minimizeToTray(self) -> None:
        """最小化到系统托盘"""
        app = QGuiApplication.instance()
        if app is None:
            return
        for w in app.topLevelWindows():
            if w.isVisible():
                w.hide()
                return

    @Property(str, notify=titleChanged)
    def title(self) -> str:
        return self._title

    @Property(bool, notify=maximizedChanged)
    def maximized(self) -> bool:
        self._get_window()
        return self._maximized