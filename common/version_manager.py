"""版本管理 — 版本字符串格式化、比较、更新检查。所有运行时代码通过此模块获取版本信息。"""

from __future__ import annotations

from typing import Literal

from common.version import (
    _MAJOR,
    _MINOR,
    _PATCH,
    CHANNEL,
    CHANNEL_NUM,
    COMMIT_HASH,
    Channel,
)

VersionFormat = Literal["semver", "clean", "full", "debug", "display", "compact"]


class AppVersion:
    """语义化版本 + 发布渠道"""

    MAJOR: int = _MAJOR
    MINOR: int = _MINOR
    PATCH: int = _PATCH
    CHANNEL: Channel = CHANNEL
    CHANNEL_NUM: int = CHANNEL_NUM
    COMMIT_HASH: str = COMMIT_HASH

    @classmethod
    def get_version(cls, fmt: VersionFormat = "clean") -> str:
        """根据格式参数返回版本字符串。

        Args:
            fmt: 格式类型，支持以下值：
                - "semver":  "0.9.40"
                - "clean":   "v0.9.40"
                - "full":    "v0.9.40-alpha.1-abc1234" / "v0.9.40"
                - "debug":   "v0.9.40-alpha.1-abc1234" / "v0.9.40-abc1234"
                - "display": "v0.9.40-alpha.1（内部测试版）" / "v0.9.40"
                - "compact": "0940"
        """
        _dispatch = {
            "semver": cls._fmt_semver,
            "clean": cls._fmt_clean,
            "full": cls._fmt_full,
            "debug": cls._fmt_debug,
            "display": cls._fmt_display,
            "compact": cls._fmt_compact,
        }
        return _dispatch[fmt]()

    # 格式化实现

    @classmethod
    def _fmt_semver(cls) -> str:
        return f"{cls.MAJOR}.{cls.MINOR}.{cls.PATCH}"

    @classmethod
    def _fmt_clean(cls) -> str:
        return f"v{cls.MAJOR}.{cls.MINOR}.{cls.PATCH}"

    @classmethod
    def _fmt_full(cls) -> str:
        """完整版本字符串。开发模式: v0.9.27-dev, 预发布: v0.9.27-alpha.1-1a2b3c4, 正式版: v0.9.27"""
        base = cls._fmt_clean()
        if cls.CHANNEL == Channel.DEV:
            return f"{base}-dev"
        if cls.CHANNEL != Channel.RELEASE:
            base += f"-{cls.CHANNEL.value}.{cls.CHANNEL_NUM}"
            if cls.COMMIT_HASH:
                base += f"-{cls.COMMIT_HASH}"
        return base

    @classmethod
    def _fmt_debug(cls) -> str:
        """调试用版本字符串。正式版附加 commit hash，预发布同 full。"""
        base = cls._fmt_full()
        if cls.COMMIT_HASH and cls.CHANNEL == Channel.RELEASE:
            base += f"-{cls.COMMIT_HASH}"
        return base

    @classmethod
    def _fmt_display(cls) -> str:
        """用户友好版本字符串。"""
        if cls.CHANNEL == Channel.RELEASE:
            return cls._fmt_full()
        return f"{cls._fmt_full()}（{cls.CHANNEL.label}）"

    @classmethod
    def _fmt_compact(cls) -> str:
        """紧凑版本号，如 '0940'"""
        return f"{cls.MAJOR}{cls.MINOR}{cls.PATCH}"

    # 旧方法别名（保持兼容）

    @classmethod
    def string(cls) -> str:
        return cls.get_version("full")

    @classmethod
    def clean(cls) -> str:
        return cls.get_version("clean")

    @classmethod
    def debug_string(cls) -> str:
        return cls.get_version("debug")

    @classmethod
    def semver(cls) -> str:
        return cls.get_version("semver")

    @classmethod
    def display(cls) -> str:
        return cls.get_version("display")

    # 构建工具方法

    @classmethod
    def dist_dir_name(cls, project_name: str, channel: str, channel_num: int,
                      commit_hash: str = "", extra: str = "") -> str:
        """构建产物目录名，如 'GenshinDogFoodSweeper-v0.9.31-alpha.1-1a2b3c4'"""
        parts = [f"{project_name}-{cls._fmt_clean()}"]
        parts.append(f"{channel}.{channel_num}")
        if commit_hash:
            parts.append(commit_hash)
        if extra:
            parts.append(extra)
        return "-".join(parts)

    @classmethod
    def dist_prefix(cls, project_name: str, channel: str) -> str:
        """同渠道同版本前缀，用于匹配旧产物。如 'GenshinDogFoodSweeper-v0.9.31-alpha.'"""
        return f"{project_name}-{cls._fmt_clean()}-{channel}."

    # 版本判断

    @classmethod
    def is_prerelease(cls) -> bool:
        return cls.CHANNEL != Channel.RELEASE

    # 版本比较

    @classmethod
    def _cmp_tuple(cls) -> tuple[int, int, int, int, int]:
        """比较用的元组，渠道越正式值越大"""
        _order = {Channel.DEV: 0, Channel.ALPHA: 1, Channel.BETA: 2, Channel.RELEASE: 3}
        return (cls.MAJOR, cls.MINOR, cls.PATCH, _order[cls.CHANNEL], cls.CHANNEL_NUM)

    @classmethod
    def compare_to(cls, other: AppVersion) -> int:
        a = cls._cmp_tuple()
        b = other._cmp_tuple()
        if a < b:
            return -1
        if a > b:
            return 1
        return 0

    @classmethod
    def is_newer_than(cls, major: int, minor: int, patch: int) -> bool:
        return (cls.MAJOR, cls.MINOR, cls.PATCH) > (major, minor, patch)

    # 更新检查

    @classmethod
    def check_update(cls, latest: AppVersion) -> tuple[bool, str]:
        """检查是否有新版本。

        返回 (has_update, 提示文字)
        """
        if cls.compare_to(latest) >= 0:
            return False, "已是最新版本"
        return True, f"发现新版本 {latest.display()}，当前 {cls.display()}"