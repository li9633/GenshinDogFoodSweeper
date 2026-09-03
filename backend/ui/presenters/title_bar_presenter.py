"""TitleBar Presenter — 自绘标题栏的业务逻辑层"""

from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot


class TitleBarPresenter(QObject):
    """标题栏 Presenter

    职责：
    - 计算窗口标题（含调试模式标识、版本号等）
    - 提供标题栏按钮的业务逻辑（未来扩展）
    """

    titleChanged = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._refresh_title()

    def _refresh_title(self) -> None:
        from utils.env_manager import EnvManager
        from utils.version import AppVersion

        base = "原神狗粮清扫器"
        if EnvManager.is_debug():
            self._title = f"{base}（调试模式）"
        else:
            self._title = f"{base} {AppVersion.clean()}"
        self.titleChanged.emit()

    @Slot()
    def minimizeToTray(self) -> None:
        """最小化到系统托盘"""
        from PySide6.QtGui import QGuiApplication

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