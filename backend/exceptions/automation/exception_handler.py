"""全局异常过滤器 — 由入口显式安装

两层过滤器：
  1. sys.excepthook          — 压制已知异常的 Python traceback
  2. qInstallMessageHandler  — 压制已知异常的 QML 错误消息

已知异常（消息本身已对用户可读、并在 UI 层提示过）静默吞掉，
不再把重复的 traceback / QML 错误刷到 stderr。

注意：本模块**不在 import 时产生任何副作用**。需要在
``backend/main.py`` 里显式调用 :func:`install_exception_filters`。
"""

from __future__ import annotations

import sys
from typing import Any

from PySide6.QtCore import QtMsgType, qInstallMessageHandler

from backend.exceptions.automation.exceptions import (
    WINDOW_NOT_FOUND_MINIMIZED_MSG,
    WINDOW_NOT_FOUND_PROCESS_MSG,
    GameWindowNotFoundError,
    LockIconNotFoundError,
    OcrModelNotReadyError,
)

# 已知异常的消息文本（用于匹配 Qt/QML 错误消息）
_KNOWN_MESSAGES = (
    WINDOW_NOT_FOUND_PROCESS_MSG,
    WINDOW_NOT_FOUND_MINIMIZED_MSG,
    OcrModelNotReadyError._MESSAGE,
    LockIconNotFoundError._MESSAGE,
)

# 已知异常类型（用于匹配 Python traceback）
_HANDLED = (GameWindowNotFoundError, OcrModelNotReadyError, LockIconNotFoundError)

_installed = False


def _python_handler(
    exc_type: type[BaseException],
    exc_value: BaseException,
    exc_tb: Any,
) -> None:
    if exc_type in _HANDLED:
        return
    sys.__excepthook__(exc_type, exc_value, exc_tb)


def _qt_handler(msg_type: QtMsgType, context: object, msg: str) -> None:
    if any(known in msg for known in _KNOWN_MESSAGES):
        return
    sys.stderr.write(f"{msg}\n")


def install_exception_filters() -> None:
    """安装两层过滤器（幂等；由应用入口调用一次）"""
    global _installed
    if _installed:
        return
    sys.excepthook = _python_handler
    qInstallMessageHandler(_qt_handler)
    _installed = True
