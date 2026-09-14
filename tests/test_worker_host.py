"""WorkerHost：后台 Worker 的生命周期托管 —— 不需要游戏窗口，也不需要真实线程干活

覆盖三件事：

1. 运行期间引用保持（线程绝不在运行中被释放）；
2. 线程结束后引用清空、``busyChanged`` 通知界面；
3. 覆盖了 ``QThread.finished`` 的 Worker 会被拒绝（否则清理逻辑失效）。
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QCoreApplication, QThread, Signal

from backend.ui.presenters.worker_host import WorkerHost


@pytest.fixture(scope="module")
def app():
    """QThread 信号投递需要一个事件循环对象"""
    instance = QCoreApplication.instance()
    if instance is None:
        instance = QCoreApplication([])
    yield instance


def _drain(app) -> None:
    """把队列里的信号处理完（含线程结束通知）"""
    for _ in range(50):
        app.processEvents()


class _SlowWorker(QThread):
    """跑一会儿再结束的 Worker"""

    stepChanged = Signal(str)

    def __init__(self, ticks: int = 3) -> None:
        super().__init__()
        self._ticks = ticks
        self.stop_called = 0

    def stop(self) -> None:
        self.stop_called += 1

    def run(self) -> None:  # pragma: no cover - 线程体
        for i in range(self._ticks):
            self.stepChanged.emit(f"tick {i}")
            self.msleep(5)


class _ShadowingWorker(QThread):
    """错误示范：覆盖了 QThread.finished"""

    finished = Signal(str)

    def run(self) -> None:  # pragma: no cover - 不该被启动
        pass


def test_start_keeps_reference_until_thread_ends(app) -> None:
    host = WorkerHost()
    worker = _SlowWorker(ticks=20)

    assert host.start(worker) is True
    assert host.busy is True
    # 线程还在跑：宿主必须继续持有引用
    assert host._worker is worker

    worker.wait(2000)
    _drain(app)
    assert host.busy is False
    assert host._worker is None


def test_busy_changed_fires_on_start_and_finish(app) -> None:
    host = WorkerHost()
    seen: list[bool] = []
    host.busyChanged.connect(lambda: seen.append(host.busy))

    worker = _SlowWorker(ticks=1)
    host.start(worker)
    worker.wait(2000)
    _drain(app)

    assert seen == [True, False]


def test_start_refuses_while_busy(app) -> None:
    host = WorkerHost()
    first = _SlowWorker(ticks=20)
    second = _SlowWorker(ticks=1)

    assert host.start(first) is True
    assert host.start(second) is False  # 不打断当前任务
    assert host._worker is first

    first.wait(2000)
    _drain(app)
    assert host.start(second) is True
    second.wait(2000)
    _drain(app)


def test_start_refuses_worker_that_shadows_finished(app) -> None:
    host = WorkerHost()
    worker = _ShadowingWorker()

    assert host.start(worker) is False
    assert host.busy is False
    assert worker.isRunning() is False


def test_stop_forwards_to_worker(app) -> None:
    host = WorkerHost()
    worker = _SlowWorker(ticks=20)

    host.start(worker)
    host.stop()
    assert worker.stop_called == 1

    worker.wait(2000)
    _drain(app)

    # 空闲时 stop 是空操作，不应抛异常
    host.stop()
    assert worker.stop_called == 1
