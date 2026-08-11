"""
环境管理器
==========
读取环境变量，提供调试模式判断等便捷方法。
所有方法均为静态方法，无需实例化。
"""

from __future__ import annotations

import os

from PySide6.QtCore import Property, QObject, Signal


class EnvManager(QObject):
    """环境变量管理器 — QObject 实现，可直接暴露给 QML"""

    # ---------- 信号 ----------

    debugChanged = Signal()

    # ---------- 环境变量键名 ----------

    DEBUG_KEY = "GDFS_DEBUG_MODE"

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
        """
        获取环境变量值。

        参数:
            key: 环境变量名
            default: 未设置时的默认值

        返回:
            环境变量值或默认值
        """
        return os.environ.get(key, default)

    @staticmethod
    def get_bool(key: str, default: bool = False) -> bool:
        """
        获取布尔型环境变量。

        支持的值（不区分大小写）:
            True:  "1", "true", "yes", "on"
            False: "0", "false", "no", "off"

        参数:
            key: 环境变量名
            default: 未设置或无法解析时的默认值

        返回:
            布尔值
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
        """判断当前是否为开发调试环境"""
        return EnvManager.get_bool(EnvManager.DEBUG_KEY, default=False)