"""
日志桥接器
==========
将 loguru 日志事件桥接到状态栏和数据库。
同时提供 start_task/end_task 接口，用于钉住长时间任务的状态。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Self

from utils.logger import log

# 需要显示在状态栏的日志级别 → 显示时长（毫秒，0=永久）
_STATUS_BAR_DURATION: dict[str, int] = {
    "INFO": 2000,
    "SUCCESS": 3000,
    "WARNING": 5000,
    "ERROR": 0,
    "CRITICAL": 0,
}

# 状态栏回调: (level, message, duration_ms) -> None
_callback: Callable[[str, str, int], None] | None = None

# 状态栏 Presenter 实例（用于 start_task/end_task）
_presenter: object | None = None


def set_status_callback(cb: Callable[[str, str, int], None]) -> None:
    """注册状态栏回调（由 MainWindow 调用，主线程）"""
    global _callback
    _callback = cb


def set_presenter(presenter: object) -> None:
    """注册 StatusBarPresenter 实例（用于任务钉住）"""
    global _presenter
    _presenter = presenter


def start_task(key: str, message: str) -> None:
    """钉住一条任务消息到状态栏，同时写入文件日志和数据库。

    线程安全，可在任意线程调用。
    状态栏直接显示，不受全局日志等级影响。
    """
    log.info(f"{message}")
    if _presenter:
        _presenter.start_task(key, message)  # type: ignore[attr-defined]


def end_task(key: str, *, success: bool | None = None, message: str = "") -> None:
    """结束任务，取消钉住。同时写入文件日志和数据库。线程安全。

    Args:
        key: 任务标识（与 start_task 对应）
        success: None=无提示, True=成功提示, False=失败提示
        message: 自定义提示文本（为空则使用默认值）
    """
    log.info(f"[任务完成] {key}")
    if _presenter:
        _presenter.end_task(key, success=success, message=message)  # type: ignore[attr-defined]


class TaskContext:
    """任务上下文管理器 — 保证 start_task/end_task 配对调用。

    异常时自动捕获 str(exc) 作为失败原因，无需手动处理。

    用法::

        with TaskContext("ocr_init", "OCR 引擎预热中 …", success_message="OCR 引擎就绪"):
            self._ocr = OcrEngine.create_ocr(self._engines_dir)
        # 成功 → 状态栏显示 SUCCESS "OCR 引擎就绪"
        # 异常 → 状态栏显示 ERROR 异常消息
    """

    def __init__(self, key: str, message: str, *, success_message: str = "") -> None:
        self._key = key
        self._message = message
        self._success_message = success_message

    def __enter__(self) -> Self:
        start_task(self._key, self._message)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> bool:
        if exc_type is None:
            end_task(self._key, success=True, message=self._success_message)
        else:
            reason = str(exc_val) if exc_val else "未知错误"
            end_task(self._key, success=False, message=reason)
        return False


_sink_ids: list[int] = []


def register_sink(sink_id: int) -> None:
    """注册 sink ID，供运行时切换全局日志等级使用"""
    _sink_ids.append(sink_id)


def update_global_level(level: str) -> None:
    """运行时动态切换所有已注册 sink 的日志等级"""
    from loguru import logger
    level_no = logger.level(level).no
    for handler_id in _sink_ids:
        handler = logger._core.handlers.get(handler_id)
        if handler is not None:
            handler._levelno = level_no


def create_status_bar_sink():
    """创建 loguru sink — 仅桥接到状态栏。

    始终以 DEBUG 级别运行，不受全局日志等级影响。
    状态栏不持久化，仅临时显示。
    """

    def sink(message):
        record = message.record
        level = record["level"].name
        msg = record["message"]
        dur = _STATUS_BAR_DURATION.get(level)
        if dur is not None and _callback:
            _callback(level, msg, dur)

    return sink