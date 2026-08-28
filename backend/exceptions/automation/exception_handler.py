"""全局异常处理器 — 类似 Spring Boot @ControllerAdvice

import 本模块即自动安装两层过滤器：
  1. sys.excepthook          — 压制已知异常的 Python traceback
  2. qInstallMessageHandler  — 压制已知异常的 QML 错误消息

已知异常（已在 __init__ 中完成 log + GMessageBox 弹窗）静默吞掉，
不再打印 traceback 或 QML 错误到 stderr。
"""

import sys

from PySide6.QtCore import QtMsgType, qInstallMessageHandler

from backend.exceptions.automation.exceptions import (
    WINDOW_NOT_FOUND_MINIMIZED_MSG,
    WINDOW_NOT_FOUND_PROCESS_MSG,
    GameWindowNotFoundError,
    OcrModelNotReadyError,
)

# 已知异常的消息文本（用于匹配 Qt/QML 错误消息）
_KNOWN_MESSAGES = (
    WINDOW_NOT_FOUND_PROCESS_MSG,
    WINDOW_NOT_FOUND_MINIMIZED_MSG,
    OcrModelNotReadyError._MESSAGE,
)

# 已知异常类型（用于匹配 Python traceback）
_HANDLED = (GameWindowNotFoundError, OcrModelNotReadyError)

# ── 1. Python 层：sys.excepthook ──

_original_excepthook = sys.excepthook


def _python_handler(
    exc_type: type[BaseException],
    exc_value: BaseException,
    exc_tb: object,
) -> None:
    if exc_type in _HANDLED:
        return
    _original_excepthook(exc_type, exc_value, exc_tb)


sys.excepthook = _python_handler


# ── 2. Qt/QML 层：qInstallMessageHandler ──

def _qt_handler(msg_type: QtMsgType, context: object, msg: str) -> None:
    if any(known in msg for known in _KNOWN_MESSAGES):
        return
    sys.stderr.write(f"{msg}\n")


qInstallMessageHandler(_qt_handler)