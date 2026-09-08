"""安装程序常量与类型定义"""

from __future__ import annotations

from collections.abc import Callable

APP_NAME = "GenshinDogFoodSweeper"
APP_NAME_CN = "原神狗粮清扫器"
APP_EXE = f"{APP_NAME}.exe"
INSTALL_INFO = "install_info.txt"
REG_UNINST_KEY = rf"Software\Microsoft\Windows\CurrentVersion\Uninstall\{APP_NAME}"

ProgressCallback = Callable[[int, str], None]