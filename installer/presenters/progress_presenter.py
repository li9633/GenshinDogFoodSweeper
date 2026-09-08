"""进度页 Presenter"""

from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot

from installer.presenters.coordinator import AppCoordinator


class ProgressPresenter(QObject):
    installProgress = Signal(int, str)
    installStarted = Signal()
    installFinished = Signal(bool, str)
    modeChanged = Signal()
    installLogChanged = Signal()

    def __init__(self, coordinator: AppCoordinator, parent: QObject | None = None):
        super().__init__(parent)
        self._coord = coordinator
        coordinator.installProgress.connect(self.installProgress)
        coordinator.installStarted.connect(self.installStarted)
        coordinator.installFinished.connect(self.installFinished)
        coordinator.modeChanged.connect(self.modeChanged)
        coordinator.installLogChanged.connect(self.installLogChanged)

    @Property(str, notify=modeChanged)
    def progressTitle(self) -> str:
        if self._coord.quick_update:
            return f"正在快速更新到版本 {self._coord.version}..."
        titles = {
            "install": "正在安装...",
            "update": "正在更新...",
            "uninstall": "正在卸载...",
        }
        return titles.get(self._coord.mode, "正在安装...")

    @Property(str, notify=modeChanged)
    def progressColor(self) -> str:
        return self._coord.accentColor

    @Property(bool, notify=modeChanged)
    def showLog(self) -> bool:
        return not self._coord.quick_update

    @Property("QVariantList", notify=installLogChanged)
    def installLog(self) -> list[str]:
        return self._coord.log_lines

    @Slot()
    def quit(self) -> None:
        self._coord.quit()