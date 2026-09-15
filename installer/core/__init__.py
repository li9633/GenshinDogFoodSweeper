"""安装程序核心层
=============
纯业务逻辑，零 UI 依赖。所有模块可独立测试。
"""

from installer.core.constants import (
    APP_EXE,
    APP_NAME,
    INSTALL_INFO,
    REG_UNINST_KEY,
    ProgressCallback,
)
from installer.core.extract import extract_7z
from installer.core.installer import restart_app, run_install, run_uninstall
from installer.core.logging import get_logger
from installer.core.registry import (
    read_registry_install_dir,
    read_registry_version,
    remove_registry,
    resolve_directory,
    resolve_install_dir,
    write_registry,
)
from installer.core.shortcut import create_shortcuts, remove_shortcuts
from installer.core.utils import (
    get_default_install_dir,
    get_own_dir,
    is_frozen,
)

__all__ = [
    "APP_EXE",
    "APP_NAME",
    "INSTALL_INFO",
    "REG_UNINST_KEY",
    "ProgressCallback",
    "create_shortcuts",
    "extract_7z",
    "get_default_install_dir",
    "get_logger",
    "get_own_dir",
    "is_frozen",
    "read_registry_install_dir",
    "read_registry_version",
    "remove_registry",
    "remove_shortcuts",
    "resolve_directory",
    "resolve_install_dir",
    "restart_app",
    "run_install",
    "run_uninstall",
    "write_registry",
]