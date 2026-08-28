"""GMessageBox Python API
=======================
通过信号桥接触发 QML 侧的 GMessageBox 弹窗，提供简洁的静态方法调用：

    from ui.gmessagebox import GMessageBox
    GMessageBox.init(engine)          # 在 main.py 中初始化一次
    GMessageBox.error("错误消息")      # 任意位置调用
    GMessageBox.warning("警告消息")
    GMessageBox.info("提示消息")
    GMessageBox.success("成功消息")

实现原理：
- GMessageBoxBridge 是注册到 QML 的 QObject，携带 showMessage 信号
- MainWindow.qml 中声明 GMessageBox 并通过 Connections 监听该信号
- Python 侧调用 GMessageBox.error() → 发射信号 → QML 打开 Dialog
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from typing import ClassVar

from PySide6.QtCore import QObject, Signal
from PySide6.QtQml import QQmlApplicationEngine
from utils.logger import log

# ---- Windows API 常量 ----
_SWP_NOMOVE = 0x0002
_SWP_NOSIZE = 0x0001
_SWP_SHOWWINDOW = 0x0040
_HWND_TOPMOST = -1
_HWND_NOTOPMOST = -2


def _force_foreground(hwnd: int) -> None:
    """使用 Windows API 强制将窗口拉到前台（绕过前台锁定）

    Windows 默认禁止后台进程通过 SetForegroundWindow 抢焦点，
    但先设为 TOPMOST 再调用 SetForegroundWindow 可以绕过此限制。
    """
    user32 = ctypes.windll.user32
    user32.SetWindowPos(
        wintypes.HWND(hwnd), wintypes.HWND(_HWND_TOPMOST),
        0, 0, 0, 0, _SWP_NOMOVE | _SWP_NOSIZE | _SWP_SHOWWINDOW,
    )
    user32.SetForegroundWindow(wintypes.HWND(hwnd))
    user32.SetWindowPos(
        wintypes.HWND(hwnd), wintypes.HWND(_HWND_NOTOPMOST),
        0, 0, 0, 0, _SWP_NOMOVE | _SWP_NOSIZE,
    )


class GMessageBoxBridge(QObject):
    """信号桥：Python → QML，触发 GMessageBox 弹窗"""

    showMessage = Signal(str, str, bool)  # (msgType, msgText, bringToFront)


class GMessageBox:
    """GMessageBox 调用入口（静态方法）"""

    _bridge: ClassVar[GMessageBoxBridge | None] = None
    _main_hwnd: ClassVar[int | None] = None

    @classmethod
    def init(cls, engine: QQmlApplicationEngine) -> None:
        """初始化：在 main.py 中调用一次，传入 QML 引擎"""
        # 从 QML 上下文获取已注册的 GMessageBoxBridge
        bridge = engine.rootContext().contextProperty("GMessageBoxBridge")
        if bridge is not None:
            cls._bridge = bridge
        else:
            log.error("GMessageBoxBridge 未在 QML 上下文中找到")

        # 获取主窗口 HWND，用于 Windows API 强制前台
        root_objects = engine.rootObjects()
        if root_objects:
            cls._main_hwnd = int(root_objects[0].winId())

    @classmethod
    def error(cls, msg: str, bring_to_front: bool = True) -> None:
        cls._show("error", msg, bring_to_front)

    @classmethod
    def warning(cls, msg: str, bring_to_front: bool = True) -> None:
        cls._show("warning", msg, bring_to_front)

    @classmethod
    def info(cls, msg: str, bring_to_front: bool = False) -> None:
        cls._show("info", msg, bring_to_front)

    @classmethod
    def success(cls, msg: str, bring_to_front: bool = False) -> None:
        cls._show("success", msg, bring_to_front)

    # ---------- 内部实现 ----------

    @classmethod
    def _show(cls, msg_type: str, msg: str, bring_to_front: bool) -> None:
        if cls._bridge is None:
            log.error("GMessageBox 未初始化，请先调用 GMessageBox.init(engine)")
            return
        if bring_to_front and cls._main_hwnd is not None:
            _force_foreground(cls._main_hwnd)
        cls._bridge.showMessage.emit(msg_type, msg, bring_to_front)