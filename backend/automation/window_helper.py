"""
窗口助手 — 纯逻辑层，无 Qt 依赖
===============================
封装原神窗口的查找、聚焦、坐标转换等操作。
将窗口相关逻辑从 Presenter 中抽离，可在任意上下文中复用。
"""

from __future__ import annotations

from utils.logger import log

from backend.automation.mouse_controller import MouseController
from backend.utils.screen_capture import ScreenshotCapture


class WindowHelper:
    """窗口助手 — 封装窗口查找、聚焦、坐标转换"""

    def __init__(
        self,
        capture: ScreenshotCapture | None = None,
        mouse: MouseController | None = None,
    ):
        self._capture = capture or ScreenshotCapture()
        self._mouse = mouse or MouseController()

    # ---- 窗口查找 ----

    def get_origin(self) -> tuple[int, int]:
        """获取原神窗口左上角屏幕坐标"""
        window = self._capture.find_genshin_window()
        if window is None:
            return (0, 0)
        return (window.left, window.top)

    def get_hwnd(self) -> int | None:
        """获取原神窗口句柄"""
        window = self._capture.find_genshin_window()
        return window.hwnd if window else None

    # ---- 坐标转换 ----

    def to_absolute(self, x: int, y: int) -> tuple[int, int]:
        """将窗口相对坐标转换为屏幕绝对坐标"""
        ox, oy = self.get_origin()
        return (ox + x, oy + y)

    # ---- 窗口聚焦 ----

    def focus(self) -> bool:
        """聚焦原神窗口"""
        hwnd = self.get_hwnd()
        if hwnd is None:
            log.warning("未检测到原神窗口")
            return False
        ok = self._mouse.focus_window(hwnd)
        log.info(f"聚焦原神窗口: {'成功' if ok else '失败'}")
        return ok