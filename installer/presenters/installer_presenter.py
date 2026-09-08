"""安装程序 Presenter
==================
QML 与业务逻辑的桥接层。负责：
- 安装目录解析（注册表 → fallback 验证）
- 7z 解压并报告进度
- 快捷方式、注册表、卸载
"""

from __future__ import annotations

import ctypes
import re
import shutil
import threading
from pathlib import Path

from PySide6.QtCore import Property, QObject, Signal, Slot
from PySide6.QtGui import QGuiApplication

from installer.installer_logic import (
    APP_NAME,
    APP_NAME_CN,
    get_default_install_dir,
    resolve_install_dir,
    restart_app,
    run_install,
    run_uninstall,
)

try:
    from installer._installer_version import VERSION  # type: ignore 
except ImportError:
    VERSION = "0.0.0"


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
    oldVersionChanged = Signal()
    installLogChanged = Signal()
    freeSpaceChanged = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._install_dir = str(get_default_install_dir())
        self._mode = "install"  # install | update | uninstall
        self._quick_update = False
        self._old_version = ""
        self._version = VERSION
        self._log_lines: list[str] = []
        self._free_space: int = -1
        self._drive_valid: bool = False
        self._required_space: int = 800 * 1024 * 1024  # 800 MB
        self._update_free_space(self._install_dir)

    # ========== 属性 ==========

    @Property(str, notify=installDirChanged)
    def installDir(self) -> str:
        return self._install_dir

    @installDir.setter
    def installDir(self, value: str) -> None:
        if self._install_dir != value:
            self._install_dir = value
            self._update_free_space(value)
            self.installDirChanged.emit()
            self.freeSpaceChanged.emit()

    @Property(str, notify=freeSpaceChanged)
    def requiredSpaceText(self) -> str:
        mb = self._required_space // (1024 * 1024)
        return f"所需空间: 约 {mb} MB"

    @Property(str, notify=freeSpaceChanged)
    def freeSpaceText(self) -> str:
        if self._free_space < 0:
            return "--"
        if self._free_space == 0:
            return ""
        mb = self._free_space // (1024 * 1024)
        return f"磁盘剩余空间: {mb} MB"

    @Property(bool, notify=freeSpaceChanged)
    def canInstall(self) -> bool:
        if not self._drive_valid:
            return False
        if self._free_space <= 0:
            return True
        return self._free_space >= self._required_space * 2.5

    @Property(str, notify=freeSpaceChanged)
    def cannotInstallReason(self) -> str:
        if not self._drive_valid:
            return "盘符无效或不存在"
        if self._free_space > 0 and self._free_space < self._required_space * 2.5:
            need = self._required_space * 2.5 // (1024 * 1024)
            remain = self._free_space // (1024 * 1024)
            return f"磁盘空间不足！需要至少 {need} MB，当前仅剩 {remain} MB"
        return ""

    @staticmethod
    def _validate_drive(path_str: str) -> bool:
        m = re.match(r'^([A-Za-z]):', path_str)
        if not m:
            return False
        drive_letter = m.group(1).upper()
        drives = ctypes.windll.kernel32.GetLogicalDrives()
        return bool(drives & (1 << (ord(drive_letter) - ord('A'))))

    def _update_free_space(self, path_str: str) -> None:
        if not path_str or not self._validate_drive(path_str):
            self._free_space = -1
            self._drive_valid = False
            return
        self._drive_valid = True
        try:
            p = Path(path_str)
            while not p.exists() and p != p.anchor:
                p = p.parent
            self._free_space = shutil.disk_usage(p).free
        except (OSError, FileNotFoundError, PermissionError):
            self._free_space = -1

    @Property(str, notify=modeChanged)
    def mode(self) -> str:
        return self._mode

    @mode.setter
    def mode(self, value: str) -> None:
        if self._mode != value:
            self._mode = value
            self.modeChanged.emit()

    @Property(bool, notify=modeChanged)
    def quickUpdate(self) -> bool:
        return self._quick_update

    @quickUpdate.setter
    def quickUpdate(self, value: bool) -> None:
        if self._quick_update != value:
            self._quick_update = value
            self.modeChanged.emit()

    @Property(str, notify=oldVersionChanged)
    def oldVersion(self) -> str:
        return self._old_version

    @oldVersion.setter
    def oldVersion(self, value: str) -> None:
        if self._old_version != value:
            self._old_version = value
            self.oldVersionChanged.emit()

    @Property(str, notify=oldVersionChanged)
    def versionLabel(self) -> str:
        if self._mode in ("update", "uninstall"):
            return ""
        if self._old_version:
            return f"v{self._old_version} → v{self._version}"
        return f"版本 {self._version}"

    @Property(bool, notify=modeChanged)
    def showWelcomePage(self) -> bool:
        return self._mode in ("install", "update")

    @Property(bool, notify=modeChanged)
    def showDirectoryPage(self) -> bool:
        return self._mode == "install"

    @Property(str, notify=modeChanged)
    def actionButtonText(self) -> str:
        if self._mode == "install":
            return "安装"
        elif self._mode == "update":
            return "更新"
        elif self._mode == "uninstall":
            return "确认卸载"
        return ""

    @Property(str, notify=modeChanged)
    def progressTitle(self) -> str:
        if self._mode == "uninstall":
            return "正在卸载..."
        return "正在更新..." if self._mode == "update" else "正在安装..."

    @Property(str, notify=modeChanged)
    def finishTitle(self) -> str:
        if self._mode == "uninstall":
            return "卸载完成！"
        return "更新完成！" if self._mode == "update" else "安装完成！"

    @Property(str, notify=installDirChanged)
    def finishMessage(self) -> str:
        if self._mode == "uninstall":
            return f"{APP_NAME_CN} 已成功卸载"
        return f"{APP_NAME_CN} 已成功安装到：\n{self._install_dir}"

    @Property(bool, notify=modeChanged)
    def showFinishLaunchButton(self) -> bool:
        return self._mode != "uninstall"

    @Property(bool, notify=modeChanged)
    def autoLaunchOnFinish(self) -> bool:
        return self._quick_update

    @Property(bool, notify=modeChanged)
    def showShortcutHint(self) -> bool:
        return self._mode == "install"

    @Property(str, notify=modeChanged)
    def welcomeText(self) -> str:
        if self._mode == "update":
            return f"检测到已安装版本 {self._old_version}，\n将更新到版本 {self._version}。\n\n请点击「更新」继续。"
        return "欢迎使用原神狗粮扫荡器安装向导。\n\n本程序将引导您完成安装过程。\n请点击「下一步」继续。"

    @Property("QVariantList", notify=installLogChanged)
    def installLog(self) -> list[str]:
        return list(self._log_lines)

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
        self._update_free_space(path)

    @Slot(str)
    def checkFreeSpace(self, path: str) -> None:
        self._update_free_space(path)
        self.freeSpaceChanged.emit()

    @Slot(str)
    def selectInstallDir(self, path: str) -> None:
        """智能选择安装目录：若目录非空则自动追加子文件夹"""
        from pathlib import Path
        p = Path(path)
        try:
            if p.exists() and p.is_dir() and any(p.iterdir()):
                p = p / APP_NAME
        except (OSError, PermissionError):
            pass
        self._install_dir = str(p)
        self._update_free_space(str(p))
        self.installDirChanged.emit()

    # ========== 统一操作入口 ==========

    @Slot()
    def startAction(self) -> None:
        """根据 mode 执行安装/更新/卸载"""
        self._log_lines.clear()
        self.installLogChanged.emit()
        if self._mode == "uninstall":
            self._start_uninstall()
        else:
            self._start_install()

    def _start_install(self) -> None:
        self.installStarted.emit()
        threading.Thread(target=self._run_install, daemon=True).start()

    def _start_uninstall(self) -> None:
        self.installStarted.emit()
        threading.Thread(target=self._run_uninstall, daemon=True).start()

    def _run_install(self) -> None:
        try:
            target = Path(self._install_dir)
            run_install(
                target,
                self._version,
                self._on_progress,
                skip_shortcuts=(self._mode == "update" or self._quick_update),
            )
            self.installFinished.emit(True, "")
        except Exception as e:
            self.installFinished.emit(False, str(e))

    def _run_uninstall(self) -> None:
        try:
            target = Path(self._install_dir)
            run_uninstall(target, self._on_progress)
            self.installFinished.emit(True, "")
        except Exception as e:
            self.installFinished.emit(False, str(e))

    def _on_progress(self, pct: int, status: str) -> None:
        self.installProgress.emit(pct, status)
        self._log_lines.append(status)
        self.installLogChanged.emit()

    # ========== 兼容旧接口 ==========

    @Slot()
    def startInstall(self) -> None:
        self.startAction()

    # ========== 重启 App ==========

    @Slot()
    def launchApp(self) -> None:
        restart_app(Path(self._install_dir))
        QGuiApplication.quit()

    # ========== 退出 ==========

    @Slot()
    def quit(self) -> None:
        QGuiApplication.quit()

    # ========== 卸载（兼容旧静态方法） ==========

    @staticmethod
    def uninstall(fallback_dir: str | None = None) -> None:
        install_dir = resolve_install_dir(fallback_dir)
        if install_dir:
            run_uninstall(install_dir)