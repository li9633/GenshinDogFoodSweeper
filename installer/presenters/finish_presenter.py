"""完成页 Presenter"""

from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot

from common.constants import APP_NAME_CN
from common.resources import Resource
from installer.presenters.coordinator import AppCoordinator


class FinishPresenter(QObject):
    installDirChanged = Signal()
    modeChanged = Signal()

    def __init__(self, coordinator: AppCoordinator, parent: QObject | None = None):
        super().__init__(parent)
        self._coord = coordinator
        coordinator.installDirChanged.connect(self.installDirChanged)
        coordinator.modeChanged.connect(self.modeChanged)

    @Property(str, notify=modeChanged)
    def finishTitle(self) -> str:
        titles = {
            "install": "安装完成！",
            "update": "更新完成！",
            "uninstall": "卸载完成！",
        }
        return titles.get(self._coord.mode, "安装完成！")

    @Property(str, notify=installDirChanged)
    def finishMessage(self) -> str:
        if self._coord.mode == "uninstall":
            return f"{APP_NAME_CN} 已成功卸载"
        if self._coord.mode == "update":
            return f"已成功更新到版本 {self._coord.version}"
        return f"{APP_NAME_CN} 已成功安装到：\n{self._coord.install_dir}"

    @Property(str, notify=modeChanged)
    def finishIcon(self) -> str:
        icons = {
            "install": Resource.INSTALL_ICON_PNG,
            "update": Resource.UPDATE_ICON_PNG,
            "uninstall": Resource.UNINSTALL_ICON_PNG,
        }
        icon = icons.get(self._coord.mode, Resource.INSTALL_ICON_PNG)
        return f"file:///{icon.as_posix()}"

    @Property(bool, notify=modeChanged)
    def showFinishLaunchButton(self) -> bool:
        return self._coord.mode != "uninstall"

    @Property(bool, notify=modeChanged)
    def autoLaunchOnFinish(self) -> bool:
        return self._coord.quick_update

    @Property(bool, notify=modeChanged)
    def showShortcutHint(self) -> bool:
        return self._coord.mode == "install"

    @Slot()
    def quit(self) -> None:
        self._coord.quit()

    @Slot()
    def launchApp(self) -> None:
        self._coord.launch_app()