"""应用协调器
=========
共享状态与核心操作逻辑。每个页面 Presenter 通过协调器获取状态并触发操作。
"""

from __future__ import annotations

import ctypes
import re
import shutil
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QGuiApplication

from installer.core import (
    APP_NAME,
    get_default_install_dir,
    get_logger,
    restart_app,
    run_install,
    run_uninstall,
)

logger = get_logger(__name__)

try:
    from _installer_version import VERSION  # type: ignore
except ImportError:
    VERSION = "0.0.0"


class AppCoordinator(QObject):
    """共享状态与操作协调器。一个 App 实例只有一个。"""

    # -- 页面导航 --
    navigateRequested = Signal(str)

    # -- 安装进度 --
    installStarted = Signal()
    installProgress = Signal(int, str)
    installFinished = Signal(bool, str)

    # -- 属性变更通知 --
    modeChanged = Signal()
    installDirChanged = Signal()
    oldVersionChanged = Signal()
    installLogChanged = Signal()
    freeSpaceChanged = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._install_dir = str(get_default_install_dir())
        self._mode = "install"
        self._quick_update = False
        self._old_version = ""
        self._version = VERSION
        self._log_lines: list[str] = []
        self._free_space: int = -1
        self._drive_valid: bool = False
        self._required_space: int = self._calc_required_space()
        self._update_free_space(self._install_dir)

    # ========== 共享状态属性 ==========

    @property
    def install_dir(self) -> str:
        return self._install_dir

    @install_dir.setter
    def install_dir(self, value: str) -> None:
        if self._install_dir != value:
            self._install_dir = value
            self._update_free_space(value)
            self.installDirChanged.emit()
            self.freeSpaceChanged.emit()

    @property
    def mode(self) -> str:
        return self._mode

    @mode.setter
    def mode(self, value: str) -> None:
        if self._mode != value:
            self._mode = value
            self.modeChanged.emit()

    @property
    def quick_update(self) -> bool:
        return self._quick_update

    @quick_update.setter
    def quick_update(self, value: bool) -> None:
        if self._quick_update != value:
            self._quick_update = value
            self.modeChanged.emit()

    @property
    def old_version(self) -> str:
        return self._old_version

    @old_version.setter
    def old_version(self, value: str) -> None:
        if self._old_version != value:
            self._old_version = value
            self.oldVersionChanged.emit()

    @property
    def version(self) -> str:
        return self._version

    @property
    def log_lines(self) -> list[str]:
        return list(self._log_lines)

    @property
    def free_space(self) -> int:
        return self._free_space

    @property
    def drive_valid(self) -> bool:
        return self._drive_valid

    @property
    def required_space(self) -> int:
        return self._required_space

    # ========== 导航 ==========

    def navigate_to(self, page: str) -> None:
        self.navigateRequested.emit(page)

    # ========== 目录选择 ==========

    def set_install_dir(self, path: str) -> None:
        self._install_dir = path
        self._update_free_space(path)

    def check_free_space(self, path: str) -> None:
        self._update_free_space(path)
        self.freeSpaceChanged.emit()

    def select_install_dir(self, path: str) -> None:
        p = Path(path)
        try:
            if p.exists() and p.is_dir() and any(p.iterdir()):
                p = p / APP_NAME
        except (OSError, PermissionError):
            pass
        self._install_dir = str(p)
        self._update_free_space(str(p))
        self.installDirChanged.emit()

    # ========== 磁盘空间检查 ==========

    @staticmethod
    def _calc_required_space() -> int:
        from installer.core import get_own_dir
        archive = get_own_dir() / "app.7z"
        if archive.exists():
            return archive.stat().st_size * 3
        return 800 * 1024 * 1024

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

    # ========== 核心操作 ==========

    def start_action(self) -> None:
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
        logger.info("Install started, target=%s, version=%s", self._install_dir, self._version)
        try:
            run_install(
                Path(self._install_dir),
                self._version,
                self._on_progress,
                skip_shortcuts=(self._mode == "update" or self._quick_update),
            )
            logger.info("Install succeeded")
            self.installFinished.emit(True, "")
        except Exception as e:
            logger.exception("Install failed")
            self.installFinished.emit(False, str(e))

    def _run_uninstall(self) -> None:
        logger.info("Uninstall started, target=%s", self._install_dir)
        try:
            run_uninstall(Path(self._install_dir), self._on_progress)
            logger.info("Uninstall succeeded")
            self.installFinished.emit(True, "")
        except Exception as e:
            logger.exception("Uninstall failed")
            self.installFinished.emit(False, str(e))

    def _on_progress(self, pct: int, status: str) -> None:
        self.installProgress.emit(pct, status)
        self._log_lines.append(status)
        self.installLogChanged.emit()

    # ========== 启动 App ==========

    def launch_app(self) -> None:
        restart_app(Path(self._install_dir))
        QGuiApplication.quit()

    # ========== 退出 ==========

    @staticmethod
    def quit() -> None:
        QGuiApplication.quit()