"""
日期时间工具类
==============
项目中所有时间操作统一入口，集中管理时区与格式。
"""

from datetime import date, datetime, timedelta, timezone

# 项目统一时区: UTC+8（北京时间）
_TZ = timezone(timedelta(hours=8))

# 项目统一格式
FMT_DATETIME = "%Y-%m-%d %H:%M:%S"
FMT_DATE = "%Y-%m-%d"
FMT_TIME = "%H:%M:%S"
FMT_FILE = "%Y%m%d_%H%M%S"  # 用于文件名


class DateTimeHelper:
    """
    日期时间工具类，所有方法均为静态方法。

    使用示例:
        now = DateTimeHelper.now()           # datetime(2026, 8, 9, 22, 30, 0)
        s   = DateTimeHelper.now_str()       # "2026-08-09 22:30:00"
        d   = DateTimeHelper.today_str()     # "2026-08-09"
        ts  = DateTimeHelper.file_timestamp() # "20260809_223000"
    """

    @staticmethod
    def now() -> datetime:
        """返回当前日期时间（带时区）"""
        return datetime.now(_TZ)

    @staticmethod
    def now_str() -> str:
        """返回当前日期时间字符串，如 "2026-08-09 22:30:00" """
        return datetime.now(_TZ).strftime(FMT_DATETIME)

    @staticmethod
    def today() -> date:
        """返回当前日期"""
        return datetime.now(_TZ).date()

    @staticmethod
    def today_str() -> str:
        """返回当前日期字符串，如 "2026-08-09" """
        return datetime.now(_TZ).strftime(FMT_DATE)

    @staticmethod
    def file_timestamp() -> str:
        """返回文件名友好的时间戳，如 "20260809_223000" """
        return datetime.now(_TZ).strftime(FMT_FILE)

    @staticmethod
    def format_ts(ts: float) -> str:
        """
        格式化 Unix 时间戳为字符串。

        参数:
            ts: Unix 时间戳（秒）

        返回:
            "2026-08-09 22:30:00"
        """
        return datetime.fromtimestamp(ts, tz=_TZ).strftime(FMT_DATETIME)

    @staticmethod
    def parse(s: str) -> datetime:
        """
        解析日期时间字符串。

        参数:
            s: 如 "2026-08-09 22:30:00"

        返回:
            带时区的 datetime 对象
        """
        return datetime.strptime(s, FMT_DATETIME).replace(tzinfo=_TZ)

    @staticmethod
    def relative_time(ts: float | None) -> str:
        """
        将时间戳转为相对时间描述。

        参数:
            ts: Unix 时间戳（秒），None 或 0 表示从未

        返回:
            "刚刚" / "3分钟前" / "2小时前" / "5天前" / "2026-08-09 14:30:00" / "从未同步"
        """
        if ts is None or ts == 0:
            return "从未同步"
        dt = datetime.fromtimestamp(ts, tz=_TZ)
        now = datetime.now(_TZ)
        diff = now - dt
        if diff < timedelta(seconds=60):
            return "刚刚"
        if diff < timedelta(minutes=60):
            return f"{int(diff.total_seconds() // 60)}分钟前"
        if diff < timedelta(hours=24):
            return f"{int(diff.total_seconds() // 3600)}小时前"
        if diff < timedelta(days=30):
            return f"{diff.days}天前"
        return dt.strftime(FMT_DATETIME)