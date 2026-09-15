"""
窗口生命周期回调
================
两种注册方式，主窗口就绪后由 ``trigger_all()`` 统一触发：

1. 继承 :class:`OnWindowReady`（构造时自动注册）—— 适用于 UI 层组件；
2. ``OnWindowReady.register(callback)`` —— 适用于不属于 UI 层的组件，
   由入口显式接入，避免底层反向 import UI 层。
"""

from __future__ import annotations

from abc import ABCMeta, abstractmethod
from collections.abc import Callable
from typing import ClassVar

from PySide6.QtCore import QObject

from backend.exceptions.automation.exceptions import OcrModelNotReadyError
from backend.utils.logger import log

# QObject + ABC 混合元类
_QObjectMeta = type(QObject)


class _QABCMeta(_QObjectMeta, ABCMeta):
    """QObject + ABCMeta 混合元类"""


class OnWindowReady(metaclass=_QABCMeta):
    """窗口就绪回调接口，构造时自动注册，主窗口就绪后 trigger_all() 统一调用"""

    _instances: ClassVar[list[OnWindowReady]] = []
    _callbacks: ClassVar[list[Callable[[], None]]] = []

    def __init__(self) -> None:
        OnWindowReady._instances.append(self)

    @abstractmethod
    def on_window_ready(self) -> None:
        """窗口就绪回调"""
        ...

    @classmethod
    def register(cls, callback: Callable[[], None]) -> None:
        """注册普通回调（供非 UI 层组件由入口显式接入）"""
        cls._callbacks.append(callback)

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
        log.debug(
            f"窗口就绪，触发 {len(unique)} 个 OnWindowReady 回调"
            f" + {len(cls._callbacks)} 个显式注册回调: {names}"
        )
        for instance in unique:
            _run_callback(type(instance).__name__, instance.on_window_ready)
        for callback in cls._callbacks:
            _run_callback(getattr(callback, "__qualname__", repr(callback)), callback)


# 需要弹窗提示用户的"可操作"异常（异常本身只带消息，展示由 UI 层决定）
_USER_ACTIONABLE_ERRORS = (OcrModelNotReadyError,)


def _run_callback(name: str, callback: Callable[[], None]) -> None:
    try:
        callback()
    except Exception as exc:
        log.error(f"{name}() 异常: {exc}")
        _notify_if_user_actionable(exc)


def _notify_if_user_actionable(exc: BaseException) -> None:
    if not isinstance(exc, _USER_ACTIONABLE_ERRORS):
        return
    try:
        from backend.ui.gmessagebox import GMessageBox

        GMessageBox.error(str(exc))
    except Exception as inner:
        log.debug(f"提示弹窗失败（可能界面尚未初始化）: {inner}")
