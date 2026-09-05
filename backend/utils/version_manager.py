"""应用版本管理
==============
版本字符串格式化、比较、更新检查。

版本数据（版本号、渠道）定义在 version.py 中。
"""

from __future__ import annotations

from .version import (
    _MAJOR,
    _MINOR,
    _PATCH,
    CHANNEL,
    CHANNEL_NUM,
    COMMIT_HASH,
    Channel,
)


class AppVersion:
    """应用版本 — 语义化版本 + 发布渠道"""

    # 主版本号
    MAJOR: int = _MAJOR
    # 次版本号
    MINOR: int = _MINOR
    # 修订版本号
    PATCH: int = _PATCH
    CHANNEL: Channel = CHANNEL
    CHANNEL_NUM: int = CHANNEL_NUM
    COMMIT_HASH: str = COMMIT_HASH

    # ---------------------------------------------------------------
    # 版本字符串
    # ---------------------------------------------------------------

    @classmethod
    def string(cls) -> str:
        """完整版本字符串。

        开发模式: v0.9.27-dev
        预发布:   v0.9.27-alpha.1-1a2b3c4
        正式版:   v0.9.27
        """
        base = f"v{cls.MAJOR}.{cls.MINOR}.{cls.PATCH}"
        if cls.CHANNEL == Channel.DEV:
            return f"{base}-dev"
        if cls.CHANNEL != Channel.RELEASE:
            base += f"-{cls.CHANNEL.value}.{cls.CHANNEL_NUM}"
            if cls.COMMIT_HASH:
                base += f"-{cls.COMMIT_HASH}"
        return base

    @classmethod
    def clean(cls) -> str:
        """纯数字版本，如 'v1.0.0'"""
        return f"v{cls.MAJOR}.{cls.MINOR}.{cls.PATCH}"

    @classmethod
    def debug_string(cls) -> str:
        """调试用版本字符串，所有渠道均包含 hash（如有）。

        正式版: v0.9.27-1a2b3c4
        预发布: v0.9.27-alpha.1-1a2b3c4
        开发:   v0.9.27-dev
        """
        base = cls.string()
        if cls.COMMIT_HASH and cls.CHANNEL == Channel.RELEASE:
            base += f"-{cls.COMMIT_HASH}"
        return base

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

    @classmethod
    def dist_dir_name(cls, project_name: str, channel: str, channel_num: int,
                      commit_hash: str = "", extra: str = "") -> str:
        """构建产物目录名，如 'GenshinDogFoodSweeper-v0.9.31-alpha.1-1a2b3c4'"""
        parts = [f"{project_name}-{cls.clean()}"]
        parts.append(f"{channel}.{channel_num}")
        if commit_hash:
            parts.append(commit_hash)
        if extra:
            parts.append(extra)
        return "-".join(parts)

    @classmethod
    def dist_prefix(cls, project_name: str, channel: str) -> str:
        """同渠道同版本前缀，用于匹配旧产物。如 'GenshinDogFoodSweeper-v0.9.31-alpha.'"""
        return f"{project_name}-{cls.clean()}-{channel}."

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