"""
状态栏 Presenter
===============
将日志消息桥接到 QML 状态栏组件，支持颜色编码和线程安全。
"""

from __future__ import annotations

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

# 日志级别 → 文字颜色，对齐 loguru 默认配色
_LEVEL_COLORS: dict[str, str] = {
    "DEBUG": "#3498DB",
    "INFO": "#B8B5C0",
    "SUCCESS": "#27AE60",
    "WARNING": "#F39C12",
    "ERROR": "#E74C3C",
    "CRITICAL": "#C0392B",
}

# 日志级别 → 背景色（暗色主题下）
_LEVEL_BG: dict[str, str] = {
    "DEBUG": "#1B2A3A",
    "INFO": "#1E1F2E",
    "SUCCESS": "#1B2E20",
    "WARNING": "#2E2A1B",
    "ERROR": "#311B1B",
    "CRITICAL": "#3C1A1A",
}


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
        self._level = "INFO"
        self._visible = True
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

    @Property(str, notify=messageChanged)
    def textColor(self) -> str:
        return _LEVEL_COLORS.get(self._level.upper(), "#B8B5C0")

    @Property(str, notify=messageChanged)
    def backgroundColor(self) -> str:
        return _LEVEL_BG.get(self._level.upper(), "#1E1F2E")

    @Property(bool, notify=messageChanged)
    def dismissable(self) -> bool:
        return self._level.upper() in ("ERROR", "CRITICAL")

    # ========== 公开方法 ==========

    def show(self, level: str, message: str, duration: int = 0) -> None:
        """线程安全：通过信号调度到主线程

        参数顺序与 log_bridge 回调一致: (level, message, duration)
        """
        self._signal.emit(level, message, duration)

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
        self.messageChanged.emit()
        self.visibleChanged.emit()

        if duration > 0:
            self._timer.start(duration)

    def _reset_to_default(self) -> None:
        self._timer.stop()
        self._level = "INFO"
        self._message = "就绪"
        self.messageChanged.emit()