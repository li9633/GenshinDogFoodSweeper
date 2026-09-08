"""安装程序日志工具
提供模块级 logger 获取函数，避免直接使用 root logger。
"""

from __future__ import annotations

import logging


def get_logger(name: str) -> logging.Logger:
    """返回以 `installer.` 为前缀的命名 logger。

    Usage:
        from installer.core.logging import get_logger
        logger = get_logger(__name__)
        logger.info("...")
    """
    if not name.startswith("installer."):
        name = f"installer.{name}"
    return logging.getLogger(name)