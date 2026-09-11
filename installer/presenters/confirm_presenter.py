"""卸载确认页 Presenter"""

from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot

from common.constants import APP_NAME_CN
from common.resources import Resource
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

    @Property(str, notify=modeChanged)
    def pageTitle(self) -> str:
        return f"卸载 {APP_NAME_CN}"

    @Property(str, notify=installDirChanged)
    def installDir(self) -> str:
        return self._coord.install_dir

    @Property(str, notify=modeChanged)
    def warningText(self) -> str:
        return (
            f"即将从以下位置移除 {APP_NAME_CN}：\n"
            f"{self._coord.install_dir}\n\n"
            "此操作将删除所有程序文件。\n"
            "您的个人数据不会被删除。"
        )

    @Property(str, notify=modeChanged)
    def actionButtonText(self) -> str:
        return "确认卸载"

    @Property(str, notify=modeChanged)
    def pageIcon(self) -> str:
        return f"file:///{Resource.UNINSTALL_ICON_PNG.as_posix()}"

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