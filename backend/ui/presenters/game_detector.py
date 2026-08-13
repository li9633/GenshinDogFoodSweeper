"""游戏进程检测器 — 轮询原神窗口，暴露给 QML"""

from PySide6.QtCore import Property, QObject, QTimer, Signal

from backend.utils.screen_capture import ScreenshotCapture


class GameDetector(QObject):
    """每 2 秒检测一次原神窗口，通过 isRunning 属性通知 QML"""

    runningChanged = Signal()
    windowChanged = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._running = False
        self._win_left = 0
        self._win_top = 0
        self._win_width = 0
        self._win_height = 0
        self._capture = ScreenshotCapture()

        self._timer = QTimer(self)
        self._timer.setInterval(2000)
        self._timer.timeout.connect(self._check)
        self._timer.start()
        self._check()

    def _check(self) -> None:
        window = self._capture.find_genshin_window()
        running = window is not None
        if running != self._running:
            self._running = running
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