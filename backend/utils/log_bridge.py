"""
日志桥接器
==========
将 loguru 日志事件桥接到状态栏和数据库。
同时提供 start_task/end_task 接口，用于钉住长时间任务的状态。
"""

from __future__ import annotations

from collections.abc import Callable

from database.repository.log_repo import LogRepo
from utils.logger import log

# 需要显示在状态栏的日志级别 → 显示时长（毫秒，0=永久）
_STATUS_BAR_DURATION: dict[str, int] = {
    "INFO": 3000,
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


def start_task(key: str, level: str, message: str) -> None:
    """钉住一条任务消息到状态栏，同时写入文件日志和数据库。

    线程安全，可在任意线程调用。
    任务消息会保持显示直到调用 end_task()，
    期间其他日志短暂突破后会自动回退。
    """
    log.info(f"[任务开始] {message}")
    if _presenter:
        _presenter.start_task(key, level, message)  # type: ignore[attr-defined]


def end_task(key: str) -> None:
    """结束任务，取消钉住。同时写入文件日志和数据库。线程安全。"""
    log.info(f"[任务完成] {key}")
    if _presenter:
        _presenter.end_task(key)  # type: ignore[attr-defined]


def create_db_sink():
    """创建 loguru sink — 同时写入 DB + 状态栏"""

    def sink(message):
        record = message.record
        level = record["level"].name
        msg = record["message"]
        module = record["name"]

        # 1. 持久化到 DB
        try:
            LogRepo.insert(level, msg, module)
        except Exception:  # noqa: S110
            pass

        # 2. 回调状态栏（sink 在 log.info() 调用线程同步执行）
        dur = _STATUS_BAR_DURATION.get(level)
        if dur is not None and _callback:
            _callback(level, msg, dur)

    return sink