"""
窗口助手 — 纯逻辑层，无 Qt 依赖
===============================
封装原神窗口的查找、聚焦、坐标转换等操作。
所有窗口相关逻辑的唯一入口，不依赖截图模块。

设计原则：
  - WindowHelper 是窗口信息的唯一真相来源
  - screen_capture 只负责截图，接受 WindowInfo 作为输入
  - 调用方先通过 WindowHelper 获取窗口信息，再传给 screen_capture 截图
"""

from __future__ import annotations

import ctypes
import time
from dataclasses import dataclass
from pathlib import Path

from utils.logger import log

# ===================== 可选依赖检测 =====================

_HAS_WIN32 = False
try:
    import win32con
    import win32gui

    _HAS_WIN32 = True
except ImportError:
    pass

_HAS_WIN32_PROCESS = False
try:
    import win32api
    import win32process

    _HAS_WIN32_PROCESS = True
except ImportError:
    pass

_HAS_PSUTIL = False
try:
    import psutil

    _HAS_PSUTIL = True
except ImportError:
    pass


# ===================== 数据类 =====================


@dataclass
class WindowInfo:
    """窗口信息"""

    hwnd: int
    title: str
    class_name: str
    left: int
    top: int
    right: int
    bottom: int
    process_name: str = ""

    @property
    def origin(self) -> tuple[int, int]:
        """窗口左上角屏幕坐标"""
        return (self.left, self.top)

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top

    @property
    def rect(self) -> tuple[int, int, int, int]:
        return (self.left, self.top, self.right, self.bottom)

    def __repr__(self) -> str:
        return (
            f'WindowInfo(hwnd={self.hwnd}, title="{self.title}", '
            f"class={self.class_name}, {self.width}x{self.height} @ ({self.left},{self.top}))"
        )


# ===================== WindowHelper =====================


class WindowHelper:
    """窗口助手 — 封装窗口查找、聚焦、坐标转换

    纯静态工具类，所有方法直接通过类名调用：
        WindowHelper.find_genshin_window()
        WindowHelper.get_origin()
        WindowHelper.focus()
    """

    GENSHIN_TITLES = ("原神", "Genshin Impact")
    GENSHIN_CLASS = "UnityWndClass"
    GENSHIN_PROCESSES = ("GenshinImpact.exe", "YuanShen.exe")

    # ---- 内部工具 ----

    @staticmethod
    def _get_process_name(hwnd: int) -> str:
        """获取窗口所属进程的可执行文件名（如 GenshinImpact.exe）"""
        if not _HAS_WIN32_PROCESS:
            return ""
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            handle = win32api.OpenProcess(
                win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ,
                False, pid,
            )
            path = win32process.GetModuleFileNameEx(handle, 0)
            win32api.CloseHandle(handle)
            return Path(path).name
        except Exception:
            return ""

    # ---- 窗口查找 ----

    @staticmethod
    def find_genshin_window() -> WindowInfo | None:
        """查找原神游戏窗口。

        匹配策略（按优先级）：
          1. 标题精确等于 "原神" 或 "Genshin Impact"
          2. 窗口类名为 UnityWndClass（Unity 引擎）
        """
        if not _HAS_WIN32:
            return None

        exact_matches: list[WindowInfo] = []
        class_matches: list[WindowInfo] = []

        def enum_callback(hwnd, _):
            if not win32gui.IsWindowVisible(hwnd):
                return True
            title = win32gui.GetWindowText(hwnd)
            class_name = win32gui.GetClassName(hwnd)
            rect = win32gui.GetWindowRect(hwnd)
            w, h = rect[2] - rect[0], rect[3] - rect[1]
            if w < 400 or h < 300:
                return True
            proc_name = WindowHelper._get_process_name(hwnd)
            info = WindowInfo(hwnd, title, class_name, *rect, process_name=proc_name)
            if class_name == WindowHelper.GENSHIN_CLASS and (
                not proc_name or proc_name in WindowHelper.GENSHIN_PROCESSES
            ):
                class_matches.append(info)
            if title in WindowHelper.GENSHIN_TITLES:
                exact_matches.append(info)
            return True

        win32gui.EnumWindows(enum_callback, None)
        return (
            exact_matches[0]
            if exact_matches
            else (class_matches[0] if class_matches else None)
        )

    @staticmethod
    def is_genshin_process_running() -> bool:
        """检测原神游戏进程是否在运行（不关心窗口是否可见）。"""
        if not _HAS_PSUTIL:
            return False
        for proc in psutil.process_iter(["name"]):
            try:
                if proc.info["name"].lower() in (
                    p.lower() for p in WindowHelper.GENSHIN_PROCESSES
                ):
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False

    @staticmethod
    def get_window_not_found_message() -> str:
        """根据进程状态返回精准的窗口未找到提示。"""
        from backend.exceptions.automation.exceptions import (
            WINDOW_NOT_FOUND_MINIMIZED_MSG,
            WINDOW_NOT_FOUND_PROCESS_MSG,
        )

        if WindowHelper.is_genshin_process_running():
            return WINDOW_NOT_FOUND_MINIMIZED_MSG
        return WINDOW_NOT_FOUND_PROCESS_MSG

    @staticmethod
    def list_visible_windows(
        min_width: int = 200, min_height: int = 200
    ) -> list[WindowInfo]:
        """列出所有可见窗口"""
        if not _HAS_WIN32:
            return []

        windows: list[WindowInfo] = []

        def enum_callback(hwnd, _):
            if not win32gui.IsWindowVisible(hwnd):
                return True
            title = win32gui.GetWindowText(hwnd)
            if not title:
                return True
            rect = win32gui.GetWindowRect(hwnd)
            w, h = rect[2] - rect[0], rect[3] - rect[1]
            if w >= min_width and h >= min_height:
                class_name = win32gui.GetClassName(hwnd)
                windows.append(WindowInfo(hwnd, title, class_name, *rect))
            return True

        win32gui.EnumWindows(enum_callback, None)
        return windows

    # ---- 便捷方法 ----

    @staticmethod
    def get_window_info() -> WindowInfo | None:
        """获取窗口完整信息，窗口不存在时返回 None（不抛异常）

        适用于轮询 / 调试面板等需要容忍窗口不存在的场景。
        """
        return WindowHelper.find_genshin_window()

    @staticmethod
    def get_origin() -> tuple[int, int]:
        """获取原神窗口左上角屏幕坐标，窗口不存在时抛异常

        适用于分解流程等必须窗口存在的场景。
        """
        from backend.exceptions.automation import GameWindowNotFoundError

        window = WindowHelper.find_genshin_window()
        if window is None:
            raise GameWindowNotFoundError(
                WindowHelper.get_window_not_found_message()
            )
        return (window.left, window.top)

    @staticmethod
    def get_hwnd() -> int | None:
        """获取原神窗口句柄"""
        window = WindowHelper.find_genshin_window()
        return window.hwnd if window else None

    # ---- 坐标转换 ----

    @staticmethod
    def to_absolute(x: int, y: int) -> tuple[int, int]:
        """将窗口相对坐标转换为屏幕绝对坐标"""
        ox, oy = WindowHelper.get_origin()
        return (ox + x, oy + y)

    # ---- 窗口聚焦 ----

    @staticmethod
    def focus() -> bool:
        """聚焦原神窗口"""
        from backend.exceptions.automation import GameWindowNotFoundError

        hwnd = WindowHelper.get_hwnd()
        if hwnd is None:
            raise GameWindowNotFoundError(
                WindowHelper.get_window_not_found_message()
            )
        try:
            ctypes.windll.user32.SetForegroundWindow(hwnd)
            time.sleep(0.1)
            log.info("聚焦原神窗口: 成功")
            return True
        except Exception as e:
            log.warning(f"聚焦原神窗口失败: {e}")
            return False