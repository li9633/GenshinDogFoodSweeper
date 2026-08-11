"""将 Presenter 方法异步化，避免阻塞 UI 线程"""

from __future__ import annotations

import traceback
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QThread, Signal
from utils.logger import log


class AsyncRunner(QThread):
    """在后台线程执行可调用对象，通过信号返回结果"""

    result_ready = Signal(object)
    task_error = Signal(str)

    def __init__(self, fn: Callable[[], Any], parent: QObject | None = None):
        super().__init__(parent)
        self._fn = fn

    def run(self) -> None:
        log.debug("[AsyncTask] run() 开始执行")
        try:
            result = self._fn()
            log.debug("[AsyncTask] _fn() 执行完成，准备 emit result_ready")
            self.result_ready.emit(result)
            log.debug("[AsyncTask] result_ready 已 emit")
        except Exception:
            tb = traceback.format_exc()
            log.error(f"[AsyncTask] _fn() 抛出异常:\n{tb}")
            self.task_error.emit(tb)


def run_async(
    fn: Callable[[], Any],
    *,
    on_result: Callable[[Any], None] | None = None,
    on_error: Callable[[str], None] | None = None,
    parent: QObject | None = None,
) -> QThread:
    """在后台线程执行 fn()，通过回调返回结果"""
    task = AsyncRunner(fn, parent)

    if on_result:
        task.result_ready.connect(on_result)
    if on_error:
        task.task_error.connect(on_error)

    task.start()
    return task