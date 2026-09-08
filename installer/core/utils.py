"""安装程序工具函数"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from installer.core.constants import APP_NAME


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def get_own_dir() -> Path:
    """setup.exe 自身所在目录（开发模式为 installer/，打包后为 MEIPASS）"""
    if is_frozen():
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent.parent


def get_default_install_dir() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", "")) / APP_NAME