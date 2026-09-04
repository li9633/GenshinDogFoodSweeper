"""
日志配置模块
============
基于 loguru 的统一日志管理，拦截标准 logging 和 uvicorn 日志。
"""

import logging
import sys
from pathlib import Path

from loguru import logger


def setup_logging(
    log_dir: str | Path = "logs",
    level: str = "DEBUG",
    rotation: str = "10 MB",
    retention: str = "7 days",
):
    """
    配置全局日志。

    参数:
        log_dir: 日志文件目录
        level: 控制台日志级别
        rotation: 日志文件轮转大小
        retention: 日志保留时间
    """
    log_dir = Path(log_dir)
    log_dir.mkdir(exist_ok=True)

    # 移除默认 handler
    logger.remove()

    # 控制台输出（彩色）
    # 注意：PyInstaller console=False 模式下 sys.stderr 为 None
    stderr_sink_id: int | None = None
    if sys.stderr is not None:
        stderr_sink_id = logger.add(
            sys.stderr,
            level=level,
            format=(
                "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
                "<cyan>{name}</cyan> | "
                "<level>{level: <8}</level> | "
                "<level>{message}</level>"
            ),
            colorize=True,
        )

    # 文件输出（所有级别）
    file_sink_id = logger.add(
        log_dir / "app_{time:YYYY-MM-DD}.log",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
        rotation=rotation,
        retention=retention,
        encoding="utf-8",
    )

    # 错误单独记录
    logger.add(
        log_dir / "error_{time:YYYY-MM-DD}.log",
        level="ERROR",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
        rotation=rotation,
        retention=retention,
        encoding="utf-8",
    )

    # 拦截标准 logging → loguru
    _intercept_standard_logging()

    return file_sink_id, stderr_sink_id


def _intercept_standard_logging():
    """将标准 logging 模块的日志重定向到 loguru"""

    class LoguruHandler(logging.Handler):
        def emit(self, record: logging.LogRecord):
            level_no = record.levelno
            frame = logging.currentframe()
            depth = 2
            while frame and frame.f_code.co_filename == logging.__file__:
                frame = frame.f_back
                depth += 1
            logger.opt(depth=depth, exception=record.exc_info).log(
                _level_for(level_no), record.getMessage()
            )

    @staticmethod
    def _level_for(level_no: int) -> str:
        levels = {
            logging.DEBUG: "DEBUG",
            logging.INFO: "INFO",
            logging.WARNING: "WARNING",
            logging.ERROR: "ERROR",
            logging.CRITICAL: "CRITICAL",
        }
        return levels.get(level_no, "INFO")

    # 拦截 root logger
    root = logging.getLogger()
    root.handlers = [LoguruHandler()]
    root.setLevel(logging.WARNING)  # 只转发 WARNING 及以上到 loguru

    # 彻底静默 uvicorn 的 INFO 日志
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        lg = logging.getLogger(name)
        lg.handlers = []
        lg.propagate = False
        lg.setLevel(logging.WARNING)


# 模块级 logger 实例
log = logger