"""通用格式化工具

提供字节大小、网速等场景的人类可读格式化函数。
"""

from __future__ import annotations


class FormatUtils:
    """通用格式化"""

    # ── 常量 ──
    _KB: int = 1024
    _MB: int = 1048576
    _GB: int = 1073741824

    # ── 网速 ──

    @staticmethod
    def speed_bytes(byte_per_sec: float) -> str:
        """将字节/秒格式化为人类可读的网速字符串。

        Args:
            byte_per_sec: 每秒字节数

        Returns:
            "2.5 MB/s" / "480 KB/s" / "150 B/s" / ""
        """
        if byte_per_sec <= 0:
            return ""
        if byte_per_sec >= FormatUtils._MB:
            return f"{byte_per_sec / FormatUtils._MB:.1f} MB/s"
        if byte_per_sec >= FormatUtils._KB:
            return f"{byte_per_sec / FormatUtils._KB:.0f} KB/s"
        return f"{byte_per_sec:.0f} B/s"

    # ── 文件大小 ──

    @staticmethod
    def size_bytes(num_bytes: int) -> str:
        """将字节数格式化为人类可读的文件大小字符串。

        Args:
            num_bytes: 字节数

        Returns:
            "1.5 GB" / "256.0 MB" / "480 KB" / "150 B" / "0 B"
        """
        if num_bytes <= 0:
            return "0 B"
        if num_bytes >= FormatUtils._GB:
            return f"{num_bytes / FormatUtils._GB:.1f} GB"
        if num_bytes >= FormatUtils._MB:
            return f"{num_bytes / FormatUtils._MB:.1f} MB"
        if num_bytes >= FormatUtils._KB:
            return f"{num_bytes / FormatUtils._KB:.0f} KB"
        return f"{num_bytes} B"