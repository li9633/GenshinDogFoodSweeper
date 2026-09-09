"""目录选择页 Presenter"""

from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot

from installer.presenters.coordinator import AppCoordinator


class DirectoryPresenter(QObject):
    installDirChanged = Signal()
    modeChanged = Signal()
    freeSpaceChanged = Signal()

    def __init__(self, coordinator: AppCoordinator, parent: QObject | None = None):
        super().__init__(parent)
        self._coord = coordinator
        coordinator.installDirChanged.connect(self.installDirChanged)
        coordinator.modeChanged.connect(self.modeChanged)
        coordinator.freeSpaceChanged.connect(self.freeSpaceChanged)

    @Property(str, notify=installDirChanged)
    def installDir(self) -> str:
        return self._coord.install_dir

    @Property(bool, notify=modeChanged)
    def showDirectoryPage(self) -> bool:
        return self._coord.mode == "install"

    @Property(str, notify=freeSpaceChanged)
    def requiredSpaceText(self) -> str:
        mb = self._coord.required_space // (1024 * 1024)
        return f"所需空间: 约 {mb} MB"

    @Property(str, notify=freeSpaceChanged)
    def freeSpaceText(self) -> str:
        fs = self._coord.free_space
        if fs < 0:
            return "--"
        if fs == 0:
            return ""
        mb = fs // (1024 * 1024)
        return f"磁盘剩余空间: {mb} MB"

    @Property(bool, notify=freeSpaceChanged)
    def canInstall(self) -> bool:
        if not self._coord.drive_valid:
            return False
        if self._coord.free_space < 0:
            return True
        return self._coord.free_space >= self._coord.required_space * 2.5

    @Property(str, notify=freeSpaceChanged)
    def cannotInstallReason(self) -> str:
        if not self._coord.drive_valid:
            return "盘符无效或不存在"
        fs = self._coord.free_space
        rs = self._coord.required_space
        if fs > 0 and fs < rs * 2.5:
            need = rs * 2.5 // (1024 * 1024)
            remain = fs // (1024 * 1024)
            return f"磁盘空间不足！需要至少 {need} MB，当前仅剩 {remain} MB"
        return ""

    @Property(str, notify=modeChanged)
    def actionButtonText(self) -> str:
        if self._coord.mode == "install":
            return "安装"
        elif self._coord.mode == "update":
            return "更新"
        elif self._coord.mode == "uninstall":
            return "确认卸载"
        return ""

    @Slot()
    def quit(self) -> None:
        self._coord.quit()

    @Slot(str)
    def navigateTo(self, page: str) -> None:
        self._coord.navigate_to(page)

    @Slot(str)
    def selectInstallDir(self, path: str) -> None:
        self._coord.select_install_dir(path)

    @Slot(str)
    def checkFreeSpace(self, path: str) -> None:
        self._coord.check_free_space(path)

    @Slot(str)
    def setInstallDir(self, path: str) -> None:
        self._coord.set_install_dir(path)

    @Slot()
    def startInstall(self) -> None:
        self._coord.navigate_to("progress")
        self._coord.start_action()