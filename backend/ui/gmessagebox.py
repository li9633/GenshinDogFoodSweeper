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

from typing import ClassVar

from PySide6.QtCore import QObject, Signal
from PySide6.QtQml import QQmlApplicationEngine
from utils.logger import log


class GMessageBoxBridge(QObject):
    """信号桥：Python → QML，触发 GMessageBox 弹窗"""

    showMessage = Signal(str, str)  # (msgType, msgText)


class GMessageBox:
    """GMessageBox 调用入口（静态方法）"""

    _bridge: ClassVar[GMessageBoxBridge | None] = None

    @classmethod
    def init(cls, engine: QQmlApplicationEngine) -> None:
        """初始化：在 main.py 中调用一次，传入 QML 引擎"""
        # 从 QML 上下文获取已注册的 GMessageBoxBridge
        bridge = engine.rootContext().contextProperty("GMessageBoxBridge")
        if bridge is not None:
            cls._bridge = bridge
        else:
            log.error("GMessageBoxBridge 未在 QML 上下文中找到")

    @classmethod
    def error(cls, msg: str) -> None:
        cls._show("error", msg)

    @classmethod
    def warning(cls, msg: str) -> None:
        cls._show("warning", msg)

    @classmethod
    def info(cls, msg: str) -> None:
        cls._show("info", msg)

    @classmethod
    def success(cls, msg: str) -> None:
        cls._show("success", msg)

    # ---------- 内部实现 ----------

    @classmethod
    def _show(cls, msg_type: str, msg: str) -> None:
        if cls._bridge is None:
            log.error("GMessageBox 未初始化，请先调用 GMessageBox.init(engine)")
            return
        cls._bridge.showMessage.emit(msg_type, msg)