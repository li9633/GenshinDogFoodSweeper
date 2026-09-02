"""应用版本管理模块
==================
提供统一的版本号管理、发布渠道标识和版本比较功能。

开发时默认使用 Alpha 渠道，构建时通过 --channel 参数指定。

使用方式:
    from utils.version import APP_VERSION

    APP_VERSION.string()     # "v1.0.0-alpha.1"
    APP_VERSION.clean()      # "v1.0.0"
    APP_VERSION.is_prerelease()  # True
"""

from __future__ import annotations

from enum import Enum


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

def _detect_latest_channel_num(channel: str) -> int:
    """从 dist/ 目录检测同渠道已构建的最大迭代号，无产物则返回 0。"""
    from pathlib import Path

    dist_dir = Path(__file__).resolve().parents[2] / "dist"
    if not dist_dir.exists():
        return 0
    max_num = 0
    for d in dist_dir.iterdir():
        if d.is_dir() and d.name.startswith(f"GenshinDogFoodSweeper-{channel}-"):
            try:
                n = int(d.name.rsplit("-", 1)[-1])
                max_num = max(max_num, n)
            except ValueError:
                pass
    return max_num


# ---- 构建时注入的渠道配置 ----
try:
    from utils._build_channel import BUILD_CHANNEL, BUILD_CHANNEL_NUM  # type: ignore[import-untyped]  # noqa: I001

    _CHANNEL = Channel(BUILD_CHANNEL)
    _CHANNEL_NUM = BUILD_CHANNEL_NUM
except ImportError:
    _CHANNEL = Channel.ALPHA
    _CHANNEL_NUM = _detect_latest_channel_num(_CHANNEL.value)


class AppVersion:
    """应用版本 — 语义化版本 + 发布渠道

    修改版本号只需改这里，全局生效。
    """

    # 主版本号
    MAJOR: int = 0
    # 次版本号
    MINOR: int = 9
    # 修订版本号
    PATCH: int = 5
    CHANNEL: Channel = _CHANNEL
    CHANNEL_NUM: int = _CHANNEL_NUM

    # ---------------------------------------------------------------
    # 版本字符串
    # ---------------------------------------------------------------

    @classmethod
    def string(cls) -> str:
        """完整版本字符串，如 'v1.0.0-alpha.1'"""
        base = f"v{cls.MAJOR}.{cls.MINOR}.{cls.PATCH}"
        if cls.CHANNEL != Channel.RELEASE:
            base += f"-{cls.CHANNEL.value}.{cls.CHANNEL_NUM}"
        return base

    @classmethod
    def clean(cls) -> str:
        """纯数字版本，如 'v1.0.0'"""
        return f"v{cls.MAJOR}.{cls.MINOR}.{cls.PATCH}"

    @classmethod
    def semver(cls) -> str:
        """语义化版本，如 '1.0.0'（无 v 前缀）"""
        return f"{cls.MAJOR}.{cls.MINOR}.{cls.PATCH}"

    @classmethod
    def display(cls) -> str:
        """用户友好版本，如 'v1.0.0-alpha.1（内部测试版）'"""
        if cls.CHANNEL == Channel.RELEASE:
            return cls.string()
        return f"{cls.string()}（{cls.CHANNEL.label}）"

    # ---------------------------------------------------------------
    # 版本判断
    # ---------------------------------------------------------------

    @classmethod
    def is_prerelease(cls) -> bool:
        """是否为预发布版本（非正式版）"""
        return cls.CHANNEL != Channel.RELEASE

    # ---------------------------------------------------------------
    # 版本比较
    # ---------------------------------------------------------------

    @classmethod
    def _cmp_tuple(cls) -> tuple[int, int, int, int, int]:
        """比较用的元组，渠道越正式值越大"""
        _order = {Channel.DEV: 0, Channel.ALPHA: 1, Channel.BETA: 2, Channel.RELEASE: 3}
        return (cls.MAJOR, cls.MINOR, cls.PATCH, _order[cls.CHANNEL], cls.CHANNEL_NUM)

    @classmethod
    def compare_to(cls, other: AppVersion) -> int:
        """与另一个 AppVersion 比较。返回 -1（旧）/ 0（相同）/ 1（新）"""
        a = cls._cmp_tuple()
        b = other._cmp_tuple()
        if a < b:
            return -1
        if a > b:
            return 1
        return 0

    @classmethod
    def is_newer_than(cls, major: int, minor: int, patch: int) -> bool:
        """是否比指定版本新"""
        return (cls.MAJOR, cls.MINOR, cls.PATCH) > (major, minor, patch)

    # ---------------------------------------------------------------
    # 策略：当前版本是否存在更新
    # ---------------------------------------------------------------

    @classmethod
    def check_update(cls, latest: AppVersion) -> tuple[bool, str]:
        """检查是否有新版本。

        返回 (has_update, 提示文字)
        """
        if cls.compare_to(latest) >= 0:
            return False, "已是最新版本"
        return True, f"发现新版本 {latest.display()}，当前 {cls.display()}"


# 模块级便捷别名
APP_VERSION = AppVersion