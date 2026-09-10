"""欢迎页 Presenter — 安装 & 更新模式共用"""

from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot

from common.resources import Resource
from installer.core import APP_NAME_CN
from installer.presenters.coordinator import AppCoordinator


class WelcomePresenter(QObject):
    modeChanged = Signal()
    oldVersionChanged = Signal()

    def __init__(self, coordinator: AppCoordinator, parent: QObject | None = None):
        super().__init__(parent)
        self._coord = coordinator
        coordinator.modeChanged.connect(self.modeChanged)
        coordinator.oldVersionChanged.connect(self.oldVersionChanged)

    @Property(str, constant=True)
    def appName(self) -> str:
        return APP_NAME_CN

    @Property(str, notify=modeChanged)
    def pageTitle(self) -> str:
        if self._coord.mode == "update":
            return "发现新版本"
        return f"欢迎使用 {APP_NAME_CN}"

    @Property(str, notify=modeChanged)
    def pageIcon(self) -> str:
        if self._coord.mode == "update":
            return f"file:///{Resource.UPDATE_ICON_PNG.as_posix()}"
        return f"file:///{Resource.INSTALL_ICON_PNG.as_posix()}"

    @Property(str, notify=oldVersionChanged)
    def versionLabel(self) -> str:
        if self._coord.mode == "update":
            return f"v{self._coord.old_version} → v{self._coord.version}"
        if self._coord.old_version:
            return f"v{self._coord.old_version} → v{self._coord.version}"
        return f"版本 {self._coord.version}"

    @Property(bool, notify=modeChanged)
    def isUpdateMode(self) -> bool:
        return self._coord.mode == "update"

    @Property(str, notify=modeChanged)
    def welcomeText(self) -> str:
        if self._coord.mode == "update":
            return (
                f"检测到已安装版本 {self._coord.old_version}，\n"
                f"将更新到版本 {self._coord.version}。\n\n"
                "更新不会影响您的个人数据。\n"
                "请点击「开始更新」继续。"
            )
        return "欢迎使用原神狗粮扫荡器安装向导。\n\n本程序将引导您完成安装过程。\n请点击「下一步」继续。"

    @Property(str, notify=modeChanged)
    def actionButtonText(self) -> str:
        return "开始更新" if self._coord.mode == "update" else "下一步"

    @Property(str, constant=True)
    def mode(self) -> str:
        return self._coord.mode

    @Slot()
    def quit(self) -> None:
        self._coord.quit()

    @Slot(str)
    def navigateTo(self, page: str) -> None:
        self._coord.navigate_to(page)

    @Slot()
    def nextStep(self) -> None:
        if self._coord.mode == "update":
            self._coord.navigate_to("progress")
            self._coord.start_action()
        else:
            self._coord.navigate_to("directory")