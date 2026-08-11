"""
日志桥接器
==========
将 loguru 日志事件桥接到状态栏和数据库。
"""

from __future__ import annotations

from collections.abc import Callable

from database.repository.log_repo import LogRepo

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


def set_status_callback(cb: Callable[[str, str, int], None]) -> None:
    """注册状态栏回调（由 MainWindow 调用，主线程）"""
    global _callback
    _callback = cb


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