"""
状态栏 Presenter
===============
将日志消息桥接到 QML 状态栏组件，支持颜色编码和线程安全。
"""

from __future__ import annotations

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot


class StatusBarPresenter(QObject):
    """状态栏 Presenter — 线程安全，供 QML 绑定"""

    # 内部调度信号（跨线程安全）
    _signal = Signal(str, str, int)

    # QML 属性通知信号
    messageChanged = Signal()
    visibleChanged = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._message = "就绪"
        self._level = ""
        self._visible = True
        self._show_level = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._reset_to_default)
        self._signal.connect(self._do_show)

    # ========== QML 属性 ==========

    @Property(bool, notify=visibleChanged)
    def visible(self) -> bool:
        return self._visible

    @Property(str, notify=messageChanged)
    def message(self) -> str:
        return self._message

    @Property(str, notify=messageChanged)
    def level(self) -> str:
        return self._level

    @Property(bool, notify=messageChanged)
    def showLevel(self) -> bool:
        return self._show_level

    @Property(bool, notify=messageChanged)
    def dismissable(self) -> bool:
        return self._level.upper() in ("ERROR", "CRITICAL")

    # ========== 公开方法 ==========

    def show(self, level: str, message: str, duration: int = 0) -> None:
        """线程安全：通过信号调度到主线程

        参数顺序与 log_bridge 回调一致: (level, message, duration)
        """
        self._signal.emit(level, message, duration)

    @Slot(str)
    def testLog(self, level: str) -> None:
        """调试面板：通过 log.xxx 发送消息，测试完整的日志桥接链路"""
        from utils.logger import log

        msg = f"[调试] 状态栏颜色测试 — {level}"
        if level == "SUCCESS":
            log.success(msg)
        elif level == "WARNING":
            log.warning(msg)
        elif level == "ERROR":
            log.error(msg)
        elif level == "CRITICAL":
            log.critical(msg)
        else:
            log.info(msg)

    @Slot()
    def dismiss(self) -> None:
        """QML 调用：手动关闭状态栏"""
        self._hide()

    # ========== 内部实现 ==========

    def _do_show(self, level: str, message: str, duration: int) -> None:
        self._timer.stop()
        self._level = level.upper()
        self._message = message
        self._visible = True
        self._show_level = True
        self.messageChanged.emit()
        self.visibleChanged.emit()

        if duration > 0:
            self._timer.start(duration)

    def _reset_to_default(self) -> None:
        self._timer.stop()
        self._level = ""
        self._message = "就绪"
        self._show_level = False
        self.messageChanged.emit()