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

from pynput.keyboard import GlobalHotKeys
from PySide6.QtCore import QObject, Signal
from utils.logger import log


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

    # 默认热键组合：Ctrl + Shift + X
    DEFAULT_HOTKEY: str = "<ctrl>+<shift>+x"

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
        self._last_trigger = 0.0
        self._start()

    # ------------------------------------------------------------------
    # 内部实现
    # ------------------------------------------------------------------

    def _start(self) -> None:
        """启动 pynput 全局热键监听"""
        try:
            self._listener = GlobalHotKeys(
                {
                    self.DEFAULT_HOTKEY: self._on_hotkey,
                }
            )
            self._listener.start()
            log.info(f"全局热键监听已启动: {self.DEFAULT_HOTKEY}")
        except Exception as exc:
            log.error(f"全局热键监听启动失败: {exc}")

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