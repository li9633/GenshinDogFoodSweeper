"""游戏进程检测器 — 轮询原神窗口，暴露给 QML"""

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from backend.automation.window_helper import WindowHelper


class GameDetector(QObject):
    """每 2 秒检测一次原神窗口，通过 isRunning 属性通知 QML

    三态检测：
    - 进程未运行 → isRunning=False, statusText="请先启动原神"
    - 进程运行但窗口不可见 → isRunning=False, statusText="原神窗口已最小化"
    - 窗口可见 → isRunning=True,  statusText="原神已启动"
    """

    runningChanged = Signal()
    windowChanged = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._running = False
        self._process_running = False
        self._win_left = 0
        self._win_top = 0
        self._win_width = 0
        self._win_height = 0

        self._timer = QTimer(self)
        self._timer.setInterval(2000)
        self._timer.timeout.connect(self._check)
        self._timer.start()
        self._check()

    def _check(self) -> None:
        window = WindowHelper.find_genshin_window()
        running = window is not None
        process_running = WindowHelper.is_genshin_process_running()

        changed = False
        if running != self._running:
            self._running = running
            changed = True
        if process_running != self._process_running:
            self._process_running = process_running
            changed = True
        if changed:
            self.runningChanged.emit()

        if running:
            left, top, w, h = window.left, window.top, window.width, window.height
            if (left, top, w, h) != (self._win_left, self._win_top, self._win_width, self._win_height):
                self._win_left = left
                self._win_top = top
                self._win_width = w
                self._win_height = h
                self.windowChanged.emit()

    @Property(bool, notify=runningChanged)
    def isRunning(self) -> bool:
        return self._running

    @Property(int, notify=windowChanged)
    def winLeft(self) -> int:
        return self._win_left

    @Property(int, notify=windowChanged)
    def winTop(self) -> int:
        return self._win_top

    @Property(int, notify=windowChanged)
    def winWidth(self) -> int:
        return self._win_width

    @Property(int, notify=windowChanged)
    def winHeight(self) -> int:
        return self._win_height

    @Property(str, notify=runningChanged)
    def statusText(self) -> str:
        if self._running:
            return "原神已启动"
        if self._process_running:
            return "原神窗口已最小化"
        return "请先启动原神"

    @Property(str, notify=runningChanged)
    def statusColor(self) -> str:
        """返回 hex 颜色字符串，供 QML 直接绑定"""
        if self._running:
            return "#6EBA7A"
        if self._process_running:
            return "#D8AA52"
        return "#D47373"

    # ========== 操作 ==========

    @Slot()
    def focusGame(self) -> None:
        """聚焦原神窗口"""
        WindowHelper.focus()