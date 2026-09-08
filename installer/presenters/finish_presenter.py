"""完成页 Presenter"""

from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot

from installer.core import APP_NAME_CN
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
        if self._coord.mode == "uninstall":
            return "卸载完成！"
        return "更新完成！" if self._coord.mode == "update" else "安装完成！"

    @Property(str, notify=installDirChanged)
    def finishMessage(self) -> str:
        if self._coord.mode == "uninstall":
            return f"{APP_NAME_CN} 已成功卸载"
        return f"{APP_NAME_CN} 已成功安装到：\n{self._coord.install_dir}"

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