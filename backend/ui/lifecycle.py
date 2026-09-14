"""
窗口生命周期回调 — 提供 OnWindowReady 抽象接口，
实现该接口的实例在构造时自动注册，主窗口就绪后统一触发回调。
"""

from __future__ import annotations

from abc import ABCMeta, abstractmethod
from typing import ClassVar

from PySide6.QtCore import QObject
from utils.logger import log

# QObject + ABC 混合元类
_QObjectMeta = type(QObject)


class _QABCMeta(_QObjectMeta, ABCMeta):
    """QObject + ABCMeta 混合元类"""


class OnWindowReady(metaclass=_QABCMeta):
    """窗口就绪回调接口，构造时自动注册，主窗口就绪后 trigger_all() 统一调用"""

    _instances: ClassVar[list[OnWindowReady]] = []

    def __init__(self) -> None:
        OnWindowReady._instances.append(self)

    @abstractmethod
    def on_window_ready(self) -> None:
        """窗口就绪回调"""
        ...

    @classmethod
    def trigger_all(cls) -> None:
        # 防止 IDE 热重载导致 _instances 累积重复实例
        seen = set()
        unique: list[OnWindowReady] = []
        for inst in cls._instances:
            if id(inst) not in seen:
                seen.add(id(inst))
                unique.append(inst)
        cls._instances = unique

        names = [type(i).__name__ for i in unique]
        log.debug(f"窗口就绪，触发 {len(unique)} 个 OnWindowReady 回调: {names}")
        for instance in unique:
            try:
                instance.on_window_ready()
            except Exception as exc:
                log.error(
                    f"{type(instance).__name__}.on_window_ready() 异常: {exc}"
                )