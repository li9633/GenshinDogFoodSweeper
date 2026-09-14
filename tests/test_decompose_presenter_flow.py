"""清理流程（Presenter 两阶段 + 批次循环）—— 用假 Worker 驱动，不需要游戏窗口

验证「宿主接管 worker 之后」的三件事：

1. 选择完成 → 等用户确认；执行完成 → 继续下一批（批次间用 QTimer 等待，不冻结界面）；
2. 阶段交替时旧线程还没退完，新 worker 不会被拒绝（否则批次循环会静默断掉）；
3. 热键/取消请求能穿透到当前 worker。
"""

from __future__ import annotations

import threading
import time
from typing import ClassVar

import pytest
from PySide6.QtCore import QCoreApplication, QThread, Signal

from backend.ui.presenters import artifact_decompose_presenter as presenter_module
from backend.ui.presenters.artifact_decompose_presenter import (
    ArtifactDecomposePresenter,
)


class _FakeRule:
    """只用到 name，够 startDecompose 过滤规则就行"""

    def __init__(self, name: str) -> None:
        self.name = name
        self.action = "keep"
        self.part = ""
        self.part_exclude = ""
        self.main_stat = ""
        self.set_name = ""
        self.sub_stats: list = []
        self.sub_count = 0
        self.priority = 0
        self.include_unactivated = False
        self.include_main_stat = False


class _FakeSelectWorker(QThread):
    stepChanged = Signal(str)
    selectCompleted = Signal(int, int, bool)
    errorOccurred = Signal(str)

    script: ClassVar[list[tuple[int, int, bool]]] = []
    instances: ClassVar[list] = []
    hold: ClassVar[bool] = False  # True 时 run() 卡住，直到 release()（模拟"线程还没退完"）
    gate: ClassVar[threading.Event] = threading.Event()

    def __init__(self, *args, **kwargs) -> None:
        super().__init__()
        self.stop_calls = 0
        type(self).instances.append(self)

    def stop(self) -> None:
        self.stop_calls += 1

    def run(self) -> None:  # pragma: no cover - 线程体
        if type(self).hold:
            type(self).gate.wait(5)
        result = type(self).script.pop(0)
        self.selectCompleted.emit(*result)


class _FakeExecuteWorker(QThread):
    stepChanged = Signal(str)
    executeCompleted = Signal(bool)
    errorOccurred = Signal(str)

    script: ClassVar[list[bool]] = []
    instances: ClassVar[list] = []

    def __init__(self, *args, **kwargs) -> None:
        super().__init__()
        self.stop_calls = 0
        type(self).instances.append(self)

    def stop(self) -> None:
        self.stop_calls += 1

    def run(self) -> None:  # pragma: no cover - 线程体
        self.executeCompleted.emit(type(self).script.pop(0))


@pytest.fixture(scope="module")
def app():
    instance = QCoreApplication.instance()
    if instance is None:
        instance = QCoreApplication([])
    yield instance


@pytest.fixture
def presenter(app, monkeypatch):
    monkeypatch.setattr(presenter_module, "SelectWorker", _FakeSelectWorker)
    monkeypatch.setattr(presenter_module, "ExecuteWorker", _FakeExecuteWorker)
    monkeypatch.setattr(
        presenter_module.DogfoodRuleRepo,
        "find_all",
        staticmethod(lambda: [_FakeRule("测试规则")]),
    )
    _FakeSelectWorker.script = []
    _FakeSelectWorker.instances = []
    _FakeSelectWorker.hold = False
    _FakeSelectWorker.gate = threading.Event()
    _FakeExecuteWorker.script = []
    _FakeExecuteWorker.instances = []

    p = ArtifactDecomposePresenter()
    # 把批次间等待压到毫秒级（生产值 25 × 100ms）
    p._BATCH_WAIT_TICKS = 3
    p._batch_timer.setInterval(1)
    yield p


def _pump(app, predicate, timeout: float = 5.0) -> bool:
    """跑事件循环直到条件成立（或超时）"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        app.processEvents()
        if predicate():
            return True
        time.sleep(0.005)
    return predicate()


def _start(presenter) -> None:
    presenter.toggleRuleSelection("测试规则")
    presenter.startDecompose()


def test_flow_finishes_in_one_batch(app, presenter) -> None:
    _FakeSelectWorker.script = [(2, 3, False)]  # 保留 2、待分解 3、无下一批
    _FakeExecuteWorker.script = [True]

    _start(presenter)
    assert _pump(app, lambda: presenter.selectionDone) is True
    assert presenter.running is True
    assert presenter.pendingDiscard == 3
    assert len(_FakeSelectWorker.instances) == 1
    # 选择阶段结束后宿主已空闲（线程真正退出）
    assert _pump(app, lambda: not presenter._host.busy) is True

    presenter.confirmDecompose()
    assert _pump(app, lambda: not presenter.running) is True
    assert presenter.totalKeep == 2
    assert presenter.totalDiscard == 3
    assert presenter.status == "完成！保留 2 件，分解 3 件"
    assert len(_FakeExecuteWorker.instances) == 1


def test_next_batch_starts_after_execute(app, presenter) -> None:
    _FakeSelectWorker.script = [(1, 4, True), (0, 0, False)]
    _FakeExecuteWorker.script = [True]

    _start(presenter)
    assert _pump(app, lambda: presenter.selectionDone) is True
    presenter.confirmDecompose()

    # 有待分解 → 进入批次间等待 → 自动开第二批选择
    assert _pump(app, lambda: len(_FakeSelectWorker.instances) == 2) is True
    assert _pump(app, lambda: presenter.selectionDone) is True
    assert presenter.totalKeep == 1
    assert presenter.totalDiscard == 4
    assert presenter.pendingDiscard == 0  # 第二批没有可分解的

    presenter.confirmDecompose()  # 无待分解 → 直接结算
    assert _pump(app, lambda: not presenter.running) is True
    assert presenter.status == "完成！保留 1 件，分解 4 件"


def test_cancel_resets_state(app, presenter) -> None:
    _FakeSelectWorker.script = [(1, 2, False)]
    _start(presenter)
    assert _pump(app, lambda: presenter.selectionDone) is True

    presenter.cancelDecompose()
    assert presenter.running is False
    assert presenter.selectionDone is False
    assert presenter.status == "已取消"


def test_hotkey_forwards_stop_to_current_worker(app, presenter) -> None:
    """线程仍在运行时，停止请求必须落到当前 worker 上"""
    _FakeSelectWorker.script = [(1, 1, False)]
    _FakeSelectWorker.hold = True  # 让 worker 一直活着，直到测试放行

    _start(presenter)
    assert _pump(app, lambda: presenter._host.busy) is True
    worker = _FakeSelectWorker.instances[0]

    presenter._on_hotkey_stop()
    assert worker.stop_calls == 1
    assert presenter._host.busy is True  # 宿主仍在托管（没有被提前释放）

    _FakeSelectWorker.gate.set()
    assert _pump(app, lambda: not presenter._host.busy) is True


def test_timer_wait_aborts_when_stopped(app, presenter) -> None:
    """等待动画期间收到停止请求 → 不再开下一批，直接收尾"""
    _FakeSelectWorker.script = [(1, 1, True)]
    _FakeExecuteWorker.script = [True]

    _start(presenter)
    assert _pump(app, lambda: presenter.selectionDone) is True

    # 模拟用户在等待期间按下热键：置位停止事件
    presenter._decomposer.stop()
    presenter.confirmDecompose()

    assert _pump(app, lambda: not presenter.running) is True
    assert presenter.status == "用户手动停止"
    assert len(_FakeSelectWorker.instances) == 1  # 没有开第二批
