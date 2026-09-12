"""应用版本数据
==============
版本号常量、渠道定义。唯一版本数据源。

版本字符串格式化、比较、更新检查见 version_manager.py。

不应被运行时代码直接导入 — 运行时代码请使用 common.version_manager.AppVersion。
"""

from __future__ import annotations

from enum import Enum

_MAJOR = 0
_MINOR = 9
_PATCH = 41


class Channel(Enum):
    """发布渠道"""

    DEV = "dev"
    ALPHA = "alpha"
    BETA = "beta"
    RELEASE = "release"

    @property
    def label(self) -> str:
        """中文标签"""
        _labels = {
            Channel.DEV: "开发版",
            Channel.ALPHA: "内部测试版",
            Channel.BETA: "公开测试版",
            Channel.RELEASE: "正式版",
        }
        return _labels[self]


# ---- 构建时注入的渠道配置 ----
try:
    from common._build_channel import (  # type: ignore[import-untyped]
        BUILD_CHANNEL,
        BUILD_CHANNEL_NUM,
        BUILD_COMMIT_HASH,
    )

    CHANNEL = Channel(BUILD_CHANNEL)
    CHANNEL_NUM = BUILD_CHANNEL_NUM
    COMMIT_HASH = BUILD_COMMIT_HASH
except ImportError:
    CHANNEL = Channel.DEV
    CHANNEL_NUM = 0
    COMMIT_HASH = ""