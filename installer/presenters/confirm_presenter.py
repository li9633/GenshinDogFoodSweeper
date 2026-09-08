"""卸载确认页 Presenter"""

from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot

from installer.core import APP_NAME_CN
from installer.presenters.coordinator import AppCoordinator


class ConfirmPresenter(QObject):
    installDirChanged = Signal()
    modeChanged = Signal()

    def __init__(self, coordinator: AppCoordinator, parent: QObject | None = None):
        super().__init__(parent)
        self._coord = coordinator
        coordinator.installDirChanged.connect(self.installDirChanged)
        coordinator.modeChanged.connect(self.modeChanged)

    @Property(str, constant=True)
    def appName(self) -> str:
        return APP_NAME_CN

    @Property(str, notify=installDirChanged)
    def installDir(self) -> str:
        return self._coord.install_dir

    @Property(str, notify=modeChanged)
    def actionButtonText(self) -> str:
        return "确认卸载"

    @Slot()
    def quit(self) -> None:
        self._coord.quit()

    @Slot(str)
    def navigateTo(self, page: str) -> None:
        self._coord.navigate_to(page)

    @Slot()
    def startUninstall(self) -> None:
        self._coord.navigate_to("progress")
        self._coord.start_action()