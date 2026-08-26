"""
Presenter 注册表
================
所有 QML ContextProperty 在此集中声明，main.py 只需调用 register_all(engine)。
"""

from __future__ import annotations

import traceback
from collections.abc import Callable
from typing import Any

from PySide6.QtQml import QQmlApplicationEngine
from utils.logger import log

# ---- 注册表条目 ----
# 格式: (ContextProperty 名称, 工厂函数, [可选的信号连接函数])
# 全部使用延迟导入，避免单个 Presenter 的依赖缺失导致整个应用崩溃


def _make_registry() -> list[tuple[str, Callable[[], Any], list[Callable]]]:
    """集中声明所有 Presenter，延迟导入避免循环依赖"""

    from utils.env_manager import EnvManager

    registry: list[tuple[str, Callable[[], Any], list[Callable]]] = [
        ("EnvManager", EnvManager, []),
    ]

    # ---- GMessageBoxBridge（信号桥，Python → QML 弹窗）----
    from ui.gmessagebox import GMessageBoxBridge

    registry.append(("GMessageBoxBridge", GMessageBoxBridge, []))

    # ---- SettingsPresenter ----
    from ui.presenters.settings_presenter import SettingsPresenter

    from backend.automation.hotkey_listener import HotkeyListener

    def _wire_settings(p: SettingsPresenter) -> None:
        HotkeyListener.instance().hotkeyCaptured.connect(p._on_hotkey_captured)

    registry.append(("SettingsPresenter", SettingsPresenter, [_wire_settings]))

    # ---- RegionMarker ----
    from ui.presenters.region_marker_presenter import RegionMarkerPresenter

    registry.append(("RegionMarker", RegionMarkerPresenter, []))

    # ---- ElementDetection ----
    from ui.presenters.element_detection_presenter import ElementDetectionPresenter

    registry.append(("ElementDetection", ElementDetectionPresenter, []))

    # ---- ArtifactRecognition ----
    from ui.presenters.artifact_recognition_presenter import (
        ArtifactRecognitionPresenter,
    )

    registry.append(("ArtifactRecognition", ArtifactRecognitionPresenter, []))

    # ---- StatusBar ----
    from ui.presenters.status_bar_presenter import StatusBarPresenter
    from utils.log_bridge import set_status_callback

    def _wire_status(p: StatusBarPresenter) -> None:
        set_status_callback(p.show)

    registry.append(("StatusBarPresenter", StatusBarPresenter, [_wire_status]))

    # ---- ArtifactScan ----
    from ui.presenters.artifact_scan_presenter import ArtifactScanPresenter

    def _wire_scan(p: ArtifactScanPresenter) -> None:
        HotkeyListener.instance().stopRequested.connect(p.stopAllOperations)

    registry.append(("ArtifactScan", ArtifactScanPresenter, [_wire_scan]))

    # ---- GameDetector ----
    from ui.presenters.game_detector import GameDetector

    registry.append(("GameDetector", GameDetector, []))

    # ---- VersionCheck ----
    from ui.presenters.version_check_presenter import VersionCheckPresenter

    registry.append(("VersionCheck", VersionCheckPresenter, []))

    # ---- RulePresenter ----
    from ui.presenters.rule_presenter import RulePresenter

    registry.append(("RulePresenter", RulePresenter, []))

    # ---- DogfoodPresenter ----
    from ui.presenters.dogfood_presenter import DogfoodPresenter

    def _wire_dogfood(p: DogfoodPresenter) -> None:
        HotkeyListener.instance().stopRequested.connect(p._on_hotkey_stop)
        HotkeyListener.register_stop_callback(p._decomposer.stop)

    registry.append(("DogfoodPresenter", DogfoodPresenter, [_wire_dogfood]))

    return registry


# ---- 公开 API ----


def register_all(engine: QQmlApplicationEngine) -> list:
    """将注册表中所有 Presenter 注入 QML 引擎。

    返回 Presenter 实例列表，调用方必须持有返回值，
    否则 QQmlContext.setContextProperty 不持有 Python 对象引用，会被 GC 回收。
    """
    presenters: list = []
    for name, factory, wires in _make_registry():
        try:
            presenter = factory()
            presenters.append(presenter)
            engine.rootContext().setContextProperty(name, presenter)
            for wire in wires:
                wire(presenter)
            log.debug(f"{name} 注册成功")
        except Exception as exc:
            traceback.print_exc()
            log.error(f"{name} 初始化失败: {exc}")
    return presenters