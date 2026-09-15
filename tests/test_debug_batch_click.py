"""调试面板「批量点击」—— 遍历骨架的第二种用法（纯点击模式）

调试面板原先自带一套逐格点击循环（``SlotIterator``），与骨架重复；
现在它只提供端口装配 + 一个"不需要详情"的策略，其余交给 ``SlotSweep``。
这里用假端口把整条链路跑通：不需要游戏窗口、不截图、不真的点击鼠标。
"""

from __future__ import annotations

import time
from typing import ClassVar

import pytest
from PySide6.QtCore import QCoreApplication

from backend.models.slot_models import DetectResult
from backend.ui.presenters.debug_panel import artifact_scan_debug_presenter as module
from backend.ui.presenters.debug_panel.artifact_scan_debug_presenter import (
    ArtifactScanDebugPresenter,
    ClickOnlyPolicy,
)
from tests.fakes import make_frame, make_slot


class _FakeScreenSource:
    """假画面来源：prepare 计数，capture 返回一张能检测出格子的图"""

    instances: ClassVar[list] = []
    next_image: object | None = make_frame()  # None = 截图失败（找不到游戏窗口）

    def __init__(self, config, capture=None) -> None:
        self.config = config
        self.capture_impl = capture
        self.prepared = 0
        self.captures = 0
        type(self).instances.append(self)

    def prepare(self) -> None:
        self.prepared += 1

    def capture(self) -> object | None:
        self.captures += 1
        return type(self).next_image


class _FakeFinder:
    slots: ClassVar[list] = []

    def __init__(self, config) -> None:
        self.config = config

    def find(self, image: object) -> DetectResult:
        return DetectResult(slots=list(type(self).slots), bottom_y=0.0, debug_infos=())


class _FakePointer:
    clicks: ClassVar[list[tuple[int, int]]] = []

    def click(self, x: int, y: int) -> None:
        type(self).clicks.append((x, y))


@pytest.fixture(scope="module")
def app():
    instance = QCoreApplication.instance()
    if instance is None:
        instance = QCoreApplication([])
    yield instance


@pytest.fixture
def presenter(app, monkeypatch):
    monkeypatch.setattr(module, "WindowScreenSource", _FakeScreenSource)
    monkeypatch.setattr(module, "DetectorSlotFinder", _FakeFinder)
    monkeypatch.setattr(module, "MousePointer", _FakePointer)
    monkeypatch.setattr(module.WindowHelper, "focus", staticmethod(lambda: None))

    _FakeScreenSource.instances = []
    _FakeScreenSource.next_image = make_frame()
    _FakeFinder.slots = [make_slot(i) for i in range(3)]
    _FakePointer.clicks = []

    p = ArtifactScanDebugPresenter()
    p.on_window_ready()
    p.setBatchClickInterval(10)
    yield p


def _pump(app, predicate, timeout: float = 5.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        app.processEvents()
        if predicate():
            return True
        time.sleep(0.005)
    return predicate()


def test_click_only_policy_is_a_valid_sweep_policy() -> None:
    from backend.contracts.sweep import SweepPolicy

    policy = ClickOnlyPolicy()
    assert isinstance(policy, SweepPolicy)
    assert policy.needs_detail() is False
    assert policy.should_click(make_slot(0)) is True


def test_batch_click_clicks_every_slot_without_detail_capture(app, presenter) -> None:
    presenter.startBatchClick()

    assert _pump(app, lambda: not presenter.batchRunning) is True
    source = _FakeScreenSource.instances[-1]
    assert source.prepared == 1
    assert source.captures == 1  # 只截一次（检测用），没有逐格详情截图
    assert len(_FakePointer.clicks) == 3
    assert presenter.batchProgress == "3/3"


def test_batch_click_stops_and_reports_zero_when_no_slots(app, presenter) -> None:
    _FakeFinder.slots = []
    presenter.startBatchClick()

    assert _pump(app, lambda: not presenter.batchRunning) is True
    assert _FakePointer.clicks == []
    assert presenter.batchProgress == ""


def test_batch_click_reports_missing_window(app, presenter) -> None:
    _FakeScreenSource.next_image = None  # 截图失败 = 找不到游戏窗口

    presenter.startBatchClick()

    assert _pump(app, lambda: not presenter.batchRunning) is True
    assert _FakePointer.clicks == []


def test_second_start_is_refused_while_running(app, presenter) -> None:
    presenter.startBatchClick()
    assert _pump(app, lambda: presenter.batchRunning) is True
    assert presenter._batch_host.busy is True
    assert presenter.batchRunning is True

    presenter.startBatchClick()  # 不打断当前任务
    assert _pump(app, lambda: not presenter.batchRunning) is True
