"""
环境管理器
==========
读取环境变量，支持 .env 文件自动加载，提供调试模式判断等便捷方法。
所有静态方法无需实例化；QObject 实例可直接暴露给 QML。
"""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Property, QObject, Signal

# 项目根目录（common/env_manager.py → 项目根）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    """从项目根目录加载 .env 文件（仅开发环境，静默忽略缺失）"""
    env_path = _PROJECT_ROOT / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv()


class EnvManager(QObject):
    """环境变量管理器 — QObject 实现，可直接暴露给 QML"""

    # ---------- 信号 ----------

    debugChanged = Signal()

    # ---------- 环境变量键名 ----------

    DEBUG_KEY = "GDFS_DEBUG_MODE"
    INSTALLER_DEBUG_KEY = "GDFS_INSTALLER_DEBUG"

    def __init__(self, parent=None):
        super().__init__(parent)

    # ---------- QML 属性 ----------

    @Property(bool, notify=debugChanged)
    def isDebug(self) -> bool:
        """QML 绑定: EnvManager.isDebug"""
        return self.is_debug()

    # ---------- 通用方法 ----------

    @staticmethod
    def get(key: str, default: str = "") -> str:
        """获取环境变量值"""
        return os.environ.get(key, default)

    @staticmethod
    def get_bool(key: str, default: bool = False) -> bool:
        """
        获取布尔型环境变量。

        支持的值（不区分大小写）:
            True:  "1", "true", "yes", "on"
            False: "0", "false", "no", "off"
        """
        val = os.environ.get(key, "").strip().lower()
        if val in ("1", "true", "yes", "on"):
            return True
        if val in ("0", "false", "no", "off", ""):
            return False
        return default

    # ---------- 快捷方法 ----------

    @staticmethod
    def is_debug() -> bool:
        """主 App 调试模式"""
        return EnvManager.get_bool(EnvManager.DEBUG_KEY, default=False)

    @staticmethod
    def is_installer_debug() -> bool:
        """安装器调试模式"""
        return EnvManager.get_bool(EnvManager.INSTALLER_DEBUG_KEY, default=False)