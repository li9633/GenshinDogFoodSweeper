"""
设置管理器
==========
封装 SettingsRepo，提供带缓存、类型安全的读写接口。

命名空间约定
-----------
所有设置 key 使用点分命名空间，如：
    ui.theme          — 界面主题
    ui.language       — 界面语言
    scan.interval     — 扫描间隔
    scan.delay        — 扫描延迟
    recognize.threshold — 识别阈值

新增设置只需在 _DEFAULTS 中添加一行，无需修改数据库表结构。
"""

from __future__ import annotations

from typing import ClassVar

from database.repository.settings_repo import SettingsRepo


class SettingsManager:
    """设置管理器 — 带内存缓存的类型安全读写"""

    # 默认值：按命名空间分组，结构清晰，新增设置只需加一行
    _DEFAULTS: ClassVar[dict[str, dict[str, str]]] = {
        "ui": {
            "theme": "light",
        },
        "data": {
            "last_sync_ts": "0",
            "last_sync_sets": "0",
            "last_sync_pieces": "0",
            "last_sync_expected": "0",
        },
    }

    def __init__(self) -> None:
        self._flat_defaults = self._flatten(self._DEFAULTS)
        self._cache: dict[str, str] = {}
        self._load_cache()

    # ---------- 内部工具 ----------

    @staticmethod
    def _flatten(nested: dict[str, dict[str, str]], prefix: str = "") -> dict[str, str]:
        """将嵌套默认值展平为 {prefix.key: value} 格式"""
        flat: dict[str, str] = {}
        for group, pairs in nested.items():
            for k, v in pairs.items():
                full_key = f"{group}.{k}"
                flat[full_key] = str(v)
        return flat

    def _load_cache(self) -> None:
        """从数据库加载全部设置到内存缓存"""
        self._cache = {**self._flat_defaults, **SettingsRepo.get_all()}

    def reload(self) -> None:
        """重新加载缓存（外部修改数据库后调用）"""
        self._load_cache()

    # ---------- 通用读写 ----------

    def get(self, key: str) -> str:
        return self._cache.get(key, self._flat_defaults.get(key, ""))

    def get_bool(self, key: str) -> bool:
        val = self.get(key).strip().lower()
        return val in ("1", "true", "yes", "on")

    def get_int(self, key: str) -> int:
        try:
            return int(self.get(key))
        except (ValueError, TypeError):
            return 0

    def set(self, key: str, value: str, type_: str = "string") -> None:
        self._cache[key] = value
        SettingsRepo.set(key, value, type_)

    def reset(self, key: str) -> None:
        """重置为默认值"""
        default = self._flat_defaults.get(key, "")
        self._cache[key] = default
        SettingsRepo.delete(key)

    # ---------- 分组操作 ----------

    def get_group(self, prefix: str) -> dict[str, str]:
        """获取某个命名空间下的所有设置，返回去掉前缀的 {key: value}"""
        prefix_dot = f"{prefix}."
        result: dict[str, str] = {}
        for k, v in self._cache.items():
            if k.startswith(prefix_dot):
                result[k[len(prefix_dot):]] = v
        return result

    def set_group(self, prefix: str, values: dict[str, str]) -> None:
        """批量设置某个命名空间下的设置"""
        for k, v in values.items():
            self.set(f"{prefix}.{k}", v)

    # ---------- 便捷方法 ----------

    def get_theme(self) -> str:
        return self.get("ui.theme")

    def set_theme(self, value: str) -> None:
        self.set("ui.theme", value)


# 模块级单例
settings = SettingsManager()