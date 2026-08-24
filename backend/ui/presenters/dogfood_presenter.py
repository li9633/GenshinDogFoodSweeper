"""狗粮清理 Presenter"""

from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot
from utils.logger import log

from backend.automation.artifact_decomposer import ArtifactDecomposer


class DogfoodPresenter(QObject):
    """狗粮清理页面的 Presenter，调用 ArtifactDecomposer"""

    statusChanged = Signal()
    runningChanged = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._running = False
        self._status = ""
        self._decomposer = ArtifactDecomposer()

    @Property(bool, notify=runningChanged)
    def running(self) -> bool:
        return self._running

    @Property(str, notify=statusChanged)
    def status(self) -> str:
        return self._status

    @Slot()
    def startDecompose(self) -> None:
        if self._running:
            log.warning("分解已在运行中")
            return
        self._running = True
        self.runningChanged.emit()

        try:
            self._set_status("正在进入分解页面...")
            ok = self._decomposer.run()
            if ok:
                self._set_status("已进入分解页面，等待后续步骤...")
            else:
                self._set_status("进入分解页面失败")
        except Exception as e:
            log.error(f"分解流程异常: {e}")
            self._set_status(f"异常: {e}")
        finally:
            self._running = False
            self.runningChanged.emit()

    def _set_status(self, msg: str) -> None:
        self._status = msg
        self.statusChanged.emit()
