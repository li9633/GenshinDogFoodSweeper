"""
全局热键监听器
==============
基于 pynput 实现全局键盘热键，支持窗口失焦时触发。
Ctrl+Shift+X → 终止当前所有自动化操作。

架构设计：
- Singleton QObject，与 OcrWorker 保持一致的设计模式
- pynput 全局热键 → Qt Signal → 各 Presenter 自行处理停止逻辑
- 防抖：300ms 冷却，防止连发误触
"""

from __future__ import annotations

from time import perf_counter
from typing import ClassVar

from pynput.keyboard import GlobalHotKeys, Key, Listener
from PySide6.QtCore import QObject, Signal
from utils.logger import log

# pynput Key 常量 → 字符串映射
_KEY_TO_STR: dict = {
    Key.ctrl: "<ctrl>", Key.ctrl_l: "<ctrl>", Key.ctrl_r: "<ctrl>",
    Key.shift: "<shift>", Key.shift_l: "<shift>", Key.shift_r: "<shift>",
    Key.alt: "<alt>", Key.alt_l: "<alt>", Key.alt_r: "<alt>",
    Key.cmd: "<cmd>", Key.cmd_l: "<cmd>", Key.cmd_r: "<cmd>",
}


class HotkeyListener(QObject):
    """全局热键监听器（Singleton）

    用法：
        listener = HotkeyListener.instance()
        listener.stopRequested.connect(presenter.stop_all)
    """

    _instance: HotkeyListener | None = None
    _stop_callbacks: ClassVar[list] = []

    # 信号：用户按下终止热键（Qt 事件循环处理，用于 UI 清理）
    stopRequested = Signal()

    # 信号：热键录制完成，携带 pynput 格式的快捷键字符串
    hotkeyCaptured = Signal(str)

    # 防抖冷却时间（秒）
    DEBOUNCE_MS: float = 0.3

    @classmethod
    def register_stop_callback(cls, callback) -> None:
        """注册停止回调，热键触发时在 pynput 线程中直接调用。

        用于绕过 Qt 事件循环阻塞：当主线程被 time.sleep() 阻塞时，
        Signal 回调无法执行，但直接回调可以立即设置停止标志。
        """
        cls._stop_callbacks.append(callback)

    @classmethod
    def unregister_stop_callback(cls, callback) -> None:
        """注销停止回调"""
        if callback in cls._stop_callbacks:
            cls._stop_callbacks.remove(callback)

    @classmethod
    def instance(cls) -> HotkeyListener:
        """获取全局唯一实例（懒加载，自动启动监听）"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def destroy_instance(cls) -> None:
        """销毁实例并停止监听"""
        if cls._instance is not None:
            cls._instance._stop()
            cls._instance = None

    def __init__(self, parent: QObject | None = None) -> None:
        if HotkeyListener._instance is not None:
            raise RuntimeError("HotkeyListener 是单例，请使用 instance()")
        super().__init__(parent)
        self._listener: GlobalHotKeys | None = None
        self._capture_listener: Listener | None = None
        self._last_trigger = 0.0
        self._start()

    # ------------------------------------------------------------------
    # 公开 API
    # ------------------------------------------------------------------

    @staticmethod
    def get_hotkey() -> str:
        """从 settings 读取当前热键"""
        from utils.settings_manager import settings
        return settings.get("hotkey.stop")

    @staticmethod
    def set_hotkey(hotkey: str) -> None:
        """持久化热键并重启监听"""
        from utils.settings_manager import settings
        settings.set("hotkey.stop", hotkey)
        if HotkeyListener._instance is not None:
            HotkeyListener._instance._restart()

    @staticmethod
    def human_readable(hotkey: str) -> str:
        """将 pynput 格式转为人类可读格式，如 <ctrl>+<shift>+x → Ctrl+Shift+X"""
        parts = hotkey.split("+")
        result: list[str] = []
        for p in parts:
            p = p.strip()
            if p.startswith("<") and p.endswith(">"):
                inner = p[1:-1]
                result.append(inner[0].upper() + inner[1:])
            else:
                result.append(p.upper())
        return "+".join(result)

    @classmethod
    def start_capture(cls) -> None:
        """开始录制下一个快捷键组合（用于设置页面修改热键）"""
        instance = cls.instance()
        if instance._capture_listener is not None:
            return
        instance._capture_keys = set()

        def on_press(key):
            try:
                if hasattr(key, "char") and key.char:
                    instance._capture_keys.add(key.char.lower())
                elif key in _KEY_TO_STR:
                    instance._capture_keys.add(_KEY_TO_STR[key])
            except Exception as exc:
                log.debug(f"快捷键录制 on_press 异常: {exc}")

        def on_release(key):
            if instance._capture_keys:
                # 排序：修饰键在前，普通键在后
                modifiers = sorted(
                    [k for k in instance._capture_keys if k.startswith("<")],
                    key=lambda x: ["<ctrl>", "<shift>", "<alt>", "<cmd>"].index(x)
                    if x in ["<ctrl>", "<shift>", "<alt>", "<cmd>"] else 999,
                )
                normals = sorted(
                    [k for k in instance._capture_keys if not k.startswith("<")]
                )
                hotkey = "+".join(modifiers + normals)
                instance._capture_keys.clear()
                instance._stop_capture()
                cls.set_hotkey(hotkey)
                instance.hotkeyCaptured.emit(hotkey)
                log.info(f"快捷键已更新: {hotkey}")
            else:
                instance._stop_capture()

        instance._capture_listener = Listener(
            on_press=on_press, on_release=on_release
        )
        instance._capture_listener.start()
        log.info("快捷键录制已启动，请按下目标组合键...")

    @classmethod
    def cancel_capture(cls) -> None:
        """取消录制"""
        if cls._instance is not None:
            cls._instance._stop_capture()

    # ------------------------------------------------------------------
    # 内部实现
    # ------------------------------------------------------------------

    def _stop_capture(self) -> None:
        if self._capture_listener is not None:
            self._capture_listener.stop()
            self._capture_listener = None
            log.info("快捷键录制已停止")

    def _start(self) -> None:
        """启动 pynput 全局热键监听"""
        hotkey = self.get_hotkey()
        try:
            self._listener = GlobalHotKeys({hotkey: self._on_hotkey})
            self._listener.start()
            log.info(f"全局热键监听已启动: {hotkey}")
        except Exception as exc:
            log.error(f"全局热键监听启动失败: {exc}")

    def _restart(self) -> None:
        """重启监听（更换热键后调用）"""
        self._stop()
        self._start()

    def _stop(self) -> None:
        """停止监听"""
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
            log.info("全局热键监听已停止")

    def _on_hotkey(self) -> None:
        """热键回调（pynput 线程中执行）"""
        now = perf_counter()
        if now - self._last_trigger < self.DEBOUNCE_MS:
            return  # 防抖：忽略过快的重复触发
        self._last_trigger = now
        log.info("用户按下终止热键，正在停止所有自动化操作...")
        # 1. 直接回调：在 pynput 线程中立即设置停止标志（绕过 Qt 事件循环阻塞）
        for cb in self._stop_callbacks:
            try:
                cb()
            except Exception as exc:
                log.debug(f"停止回调异常: {exc}")
        # 2. Signal：排队到主线程事件循环，用于 UI 清理
        self.stopRequested.emit()