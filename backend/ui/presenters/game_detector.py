"""游戏进程检测器 — 轮询原神窗口，暴露给 QML"""

from PySide6.QtCore import Property, QObject, QTimer, Signal

from backend.utils.screen_capture import ScreenshotCapture


class GameDetector(QObject):
    """每 2 秒检测一次原神窗口，通过 isRunning 属性通知 QML"""

    runningChanged = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._running = False
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

    @Property(bool, notify=runningChanged)
    def isRunning(self) -> bool:
        return self._running
