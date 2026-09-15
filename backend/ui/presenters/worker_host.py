"""后台 Worker 生命周期托管
========================
各功能原先各自手写「起线程 → 连信号 → 结束清引用」，
出过 `QThread: Destroyed while thread is still running` 这类静默崩溃。这里统一成一个主机：

- :meth:`WorkerHost.start` —— 防重复启动；结束（**QThread 原生 finished**）后清引用并
  ``deleteLater``，因此线程绝不会在运行中被释放；
- :meth:`WorkerHost.stop` —— 转发停止请求（Worker 实现 ``stop()`` 即可）；
- :attr:`WorkerHost.busy` / ``busyChanged`` —— 供 Presenter 驱动界面的"运行中"状态。

约定：被托管的 Worker **不得覆盖** ``QThread.finished``；自定义结果信号请用业务名
（如 ``scanCompleted`` / ``lockCompleted`` / ``selectCompleted``）。
"""

from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal

from backend.utils.logger import log


class WorkerHost(QObject):
    """一次只托管一个后台 Worker"""

    busyChanged = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._worker: QThread | None = None

    @property
    def busy(self) -> bool:
        """是否有后台任务正在运行"""
        return self._worker is not None

    def start(self, worker: QThread) -> bool:
        """启动 Worker；已有任务在跑时返回 False（不打断当前任务）"""
        if self._worker is not None:
            log.warning("已有后台任务在运行，忽略本次启动请求")
            return False
        if "finished" in vars(type(worker)):
            log.error(
                f"{type(worker).__name__} 覆盖了 QThread.finished，"
                f"生命周期托管会失效，请改用业务名信号"
            )
            return False

        worker.finished.connect(self._on_thread_finished)
        self._worker = worker
        self.busyChanged.emit()
        worker.start()
        return True

    def stop(self) -> None:
        """请求停止当前 Worker（未运行时为空操作）"""
        worker = self._worker
        if worker is None:
            return
        stop = getattr(worker, "stop", None)
        if callable(stop):
            stop()

    def _on_thread_finished(self) -> None:
        """线程真正结束：清引用 + 延迟销毁（此时才安全释放）"""
        worker = self._worker
        self._worker = None
        if worker is not None:
            worker.deleteLater()
        self.busyChanged.emit()
