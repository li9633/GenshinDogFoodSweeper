"""
窗口生命周期回调
================
参考大型项目设计，提供 OnWindowReady 接口：
实现此接口的实例会在主窗口初始化完毕后自动收到 on_window_ready() 回调。

用法：
    class MyPresenter(QObject, OnWindowReady):
        def __init__(self, parent=None):
            QObject.__init__(self, parent)
            OnWindowReady.__init__(self)  # 自动注册

        def on_window_ready(self) -> None:
            ...  # 必须实现，否则实例化时报 TypeError
"""

from __future__ import annotations

from abc import ABCMeta, abstractmethod
from typing import ClassVar

from PySide6.QtCore import QObject
from utils.logger import log

# 组合元类：同时兼容 QObject（Shiboken.ObjectType）和 ABC（ABCMeta）
_QObjectMeta = type(QObject)


class _QABCMeta(_QObjectMeta, ABCMeta):
    """Shiboken.ObjectType + ABCMeta 的混合元类"""


class OnWindowReady(metaclass=_QABCMeta):
    """窗口就绪回调接口（ABC）。

    实现此接口的类在 __init__ 时自动注册，
    主窗口就绪后 trigger_all() 统一调用所有实例的 on_window_ready()。
    """

    _instances: ClassVar[list[OnWindowReady]] = []

    def __init__(self) -> None:
        OnWindowReady._instances.append(self)

    @abstractmethod
    def on_window_ready(self) -> None:
        """窗口就绪回调，子类必须实现"""
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