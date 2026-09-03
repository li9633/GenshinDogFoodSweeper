"""
状态栏 Presenter
===============
将日志消息桥接到 QML 状态栏组件，支持颜色编码、线程安全和优先级队列。

优先级（从高到低）：
  CRITICAL > ERROR > TIMED（WARNING/INFO/SUCCESS） > TASK > DEFAULT

TIMED 消息会短暂突破 TASK 显示，到期后自动回退到 TASK。
ERROR/CRITICAL 关闭后也会回退到 TASK。
"""

from __future__ import annotations

from typing import ClassVar

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot


class StatusBarPresenter(QObject):
    """状态栏 Presenter — 线程安全，供 QML 绑定"""

    _instance: ClassVar[StatusBarPresenter | None] = None

    # 内部调度信号（跨线程安全）
    _signal = Signal(str, str, int)
    _task_signal = Signal(str, str, str, str)  # action, key, level, message

    # QML 属性通知信号
    messageChanged = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        StatusBarPresenter._instance = self

        self._message = "就绪"
        self._level = ""
        self._show_level = False

        self._error_active = False
        self._error_info: tuple[str, str] | None = None
        self._timed_pending: tuple[str, str, int] | None = None
        self._task_stack: dict[str, tuple[str, str]] = {}  # key → (level, message)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._on_timer_timeout)

        self._signal.connect(self._do_show)
        self._task_signal.connect(self._do_task)

    # ========== QML 属性 ==========

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

    def start_task(self, key: str, level: str, message: str) -> None:
        """钉住一条任务消息。即使期间有其他日志，任务完成后也会回退显示。

        线程安全，可在任意线程调用。
        """
        self._task_signal.emit("start", key, level, message)

    def end_task(self, key: str) -> None:
        """结束任务，取消钉住。线程安全。"""
        self._task_signal.emit("end", key, "", "")

    @Slot()
    def dismiss(self) -> None:
        """QML 调用：关闭当前错误，回退到 TASK 或默认"""
        self._error_active = False
        self._error_info = None
        self._refresh()

    # ========== 内部实现 ==========

    def _do_show(self, level: str, message: str, duration: int) -> None:
        """接收 log_bridge 转发的消息，存入对应槽位。"""
        level_up = level.upper()

        if level_up in ("ERROR", "CRITICAL"):
            self._error_active = True
            self._error_info = (level_up, message)
        elif level_up in ("WARNING", "SUCCESS", "INFO"):
            self._timed_pending = (level_up, message, duration)

        self._refresh()

    def _do_task(self, action: str, key: str, level: str, message: str) -> None:
        """处理任务钉住/取消（主线程）。"""
        if action == "start":
            self._task_stack[key] = (level.upper(), message)
        elif action == "end":
            self._task_stack.pop(key, None)
        self._refresh()

    def _on_timer_timeout(self) -> None:
        """定时消息到期，清除并回退。"""
        self._timed_pending = None
        self._refresh()

    def _refresh(self) -> None:
        """根据优先级决定显示内容。"""
        self._timer.stop()

        # 1. 未关闭的错误
        if self._error_active and self._error_info:
            level, msg = self._error_info
            self._apply(level, msg)
            return

        # 2. 定时消息（短暂突破 TASK）
        if self._timed_pending:
            level, msg, dur = self._timed_pending
            self._apply(level, msg)
            if dur > 0:
                self._timer.start(dur)
            return

        # 3. 活跃任务（兜底）
        if self._task_stack:
            keys = list(self._task_stack.keys())
            level, msg = self._task_stack[keys[-1]]
            self._apply(level, msg)
            return

        # 4. 默认
        self._apply("", "就绪")

    def _apply(self, level: str, message: str) -> None:
        """将 level/message 写入 QML 属性并通知。"""
        self._level = level
        self._message = message
        self._show_level = bool(level)
        self.messageChanged.emit()