"""安装程序 Presenter
==================
QML 与业务逻辑的桥接层。负责：
- 安装目录解析（注册表 → fallback 验证）
- 7z 解压并报告进度
- 快捷方式、注册表、卸载
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Property, QObject, Signal, Slot
from PySide6.QtGui import QGuiApplication

from installer.installer_logic import (
    APP_NAME_CN,
    do_uninstall,
    get_default_install_dir,
    install,
    quick_update,
    resolve_install_dir,
    restart_app,
)

VERSION = "0.0.0"


def _get_version() -> str:
    global VERSION
    from installer.installer_logic import get_own_dir
    info = get_own_dir() / "install_info.txt"
    if info.exists():
        for line in info.read_text(encoding="utf-8").splitlines():
            if line.startswith("version="):
                VERSION = line.split("=", 1)[1].strip()
                return VERSION
    return VERSION


class InstallerPresenter(QObject):
    """安装程序 Presenter — 注册为 QML context property"""

    # ---- 安装进度 ----
    installStarted = Signal()
    installProgress = Signal(int, str)  # percentage, status_text
    installFinished = Signal(bool, str)  # success, message

    # ---- 页面导航 ----
    navigateRequested = Signal(str)

    # ---- 属性变更通知 ----
    installDirChanged = Signal()
    modeChanged = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._install_dir = str(get_default_install_dir())
        self._mode = "install"  # install | update
        self._version = _get_version()

    # ========== 属性 ==========

    @Property(str, notify=installDirChanged)
    def installDir(self) -> str:
        return self._install_dir

    @installDir.setter
    def installDir(self, value: str) -> None:
        if self._install_dir != value:
            self._install_dir = value
            self.installDirChanged.emit()

    @Property(str, notify=modeChanged)
    def mode(self) -> str:
        return self._mode

    @mode.setter
    def mode(self, value: str) -> None:
        if self._mode != value:
            self._mode = value
            self.modeChanged.emit()

    @Property(str, constant=True)
    def version(self) -> str:
        return self._version

    @Property(str, constant=True)
    def appName(self) -> str:
        return APP_NAME_CN

    # ========== 页面导航 ==========

    @Slot(str)
    def navigateTo(self, page: str) -> None:
        self.navigateRequested.emit(page)

    # ========== 目录选择 ==========

    @Slot(str)
    def setInstallDir(self, path: str) -> None:
        self._install_dir = path

    # ========== 安装 ==========

    @Slot()
    def startInstall(self) -> None:
        self.installStarted.emit()
        try:
            target = Path(self._install_dir)
            if self._mode == "update":
                quick_update(target, self._version, self._on_progress)
            else:
                install(target, self._version, self._on_progress)
            self.installFinished.emit(True, "")
        except Exception as e:
            self.installFinished.emit(False, str(e))

    def _on_progress(self, pct: int, status: str) -> None:
        self.installProgress.emit(pct, status)

    # ========== 重启 App ==========

    @Slot()
    def launchApp(self) -> None:
        restart_app(Path(self._install_dir))
        QGuiApplication.quit()

    # ========== 退出 ==========

    @Slot()
    def quit(self) -> None:
        QGuiApplication.quit()

    # ========== 卸载 ==========

    @staticmethod
    def uninstall(fallback_dir: str | None = None) -> None:
        install_dir = resolve_install_dir(fallback_dir)
        if install_dir:
            do_uninstall(install_dir)