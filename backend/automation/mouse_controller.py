"""
鼠标控制器
==========
基于 Win32 API 的鼠标移动、点击操作。
参考 yas 项目 design，后续可扩展为完整的定位+点击+翻页系统。
"""

from __future__ import annotations

import ctypes
import time
from ctypes import wintypes

from utils.logger import log

# Win32 API 常量
INPUT_MOUSE = 0
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_WHEEL = 0x0800

# 屏幕尺寸（用于绝对坐标计算）
_SM_CXSCREEN = 0
_SM_CYSCREEN = 1


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("mi", MOUSEINPUT),
    ]


class MouseController:
    """鼠标控制器 — 基于 Win32 SendInput

    性能设计（参考 yas）：
      - move_to() 即时完成（SendInput），无 sleep
      - click() 仅 down + 10ms + up，无额外延迟
      - 每次点击耗时 ~10ms，2000 个圣遗物约 20s

    注意：原神使用 mhyprot2 反作弊驱动，可能拦截 SendInput 输入模拟。
    如果点击无效，请以管理员权限运行本程序。
    """

    # 点击间隔常量（秒）
    CLICK_DOWN_UP_DELAY = 0.01  # 按下到释放间隔

    _origin: tuple[int, int] | None = None  # 窗口原点，由外部设置

    @classmethod
    def set_origin(cls, origin: tuple[int, int] | None) -> None:
        """设置窗口原点（屏幕坐标），此后 move_to 的坐标视为窗口相对坐标。

        传入 None 则关闭坐标转换。
        推荐从 CaptureResult.window_origin 获取，确保与截图一致：
            MouseController.set_origin(result.window_origin)
        也可从 WindowHelper 获取：
            MouseController.set_origin(WindowHelper.get_origin())
        """
        cls._origin = origin

    @staticmethod
    def is_admin() -> bool:
        """检查当前进程是否以管理员权限运行"""
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False



    @staticmethod
    def screen_size() -> tuple[int, int]:
        """获取主显示器分辨率"""
        return (
            ctypes.windll.user32.GetSystemMetrics(_SM_CXSCREEN),
            ctypes.windll.user32.GetSystemMetrics(_SM_CYSCREEN),
        )

    @staticmethod
    def move_to(x: int, y: int) -> bool:
        """
        移动鼠标到坐标 (x, y)。
        若已注入 WindowHelper，则 x, y 视为窗口相对坐标并自动转换。
        使用 SendInput 绝对坐标，即时完成，无 sleep。
        """
        try:
            rel_x, rel_y = x, y  # 保存原始窗口相对坐标
            origin = MouseController._origin
            if origin is not None:
                ox, oy = origin
                x += ox
                y += oy

            pt_before = wintypes.POINT()
            ctypes.windll.user32.GetCursorPos(ctypes.byref(pt_before))

            screen_w, screen_h = MouseController.screen_size()
            abs_x = int(x * 65535 / screen_w)
            abs_y = int(y * 65535 / screen_h)

            inp = INPUT()
            inp.type = INPUT_MOUSE
            inp.mi.dx = abs_x
            inp.mi.dy = abs_y
            inp.mi.dwFlags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE

            result = ctypes.windll.user32.SendInput(
                1, ctypes.byref(inp), ctypes.sizeof(inp)
            )
            if result == 0:
                log.warning(f"SendInput 移动失败: ({x}, {y})")
                return False
            if origin is not None:
                log.debug(
                    f"鼠标移动: 窗口相对({rel_x}, {rel_y}) → 屏幕绝对({x}, {y})"
                )
            else:
                log.debug(f"鼠标移动: 屏幕绝对({pt_before.x}, {pt_before.y}) → ({x}, {y})")
            return True
        except Exception as e:
            log.error(f"鼠标移动异常: {e}")
            return False

    @staticmethod
    def click() -> bool:
        """
        鼠标左键点击（当前位置）。
        仅 down + CLICK_DOWN_UP_DELAY + up，无其他延迟。
        调用前应先 move_to() 定位。
        """
        try:
            pt = wintypes.POINT()
            ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))

            origin = MouseController._origin
            if origin is not None:
                ox, oy = origin
                log.debug(f"鼠标点击: 屏幕绝对({pt.x}, {pt.y}) 窗口相对({pt.x - ox}, {pt.y - oy})")
            else:
                log.debug(f"鼠标点击: 屏幕绝对({pt.x}, {pt.y})")

            inp_down = INPUT()
            inp_down.type = INPUT_MOUSE
            inp_down.mi.dwFlags = MOUSEEVENTF_LEFTDOWN
            r1 = ctypes.windll.user32.SendInput(
                1, ctypes.byref(inp_down), ctypes.sizeof(inp_down)
            )

            time.sleep(MouseController.CLICK_DOWN_UP_DELAY)

            inp_up = INPUT()
            inp_up.type = INPUT_MOUSE
            inp_up.mi.dwFlags = MOUSEEVENTF_LEFTUP
            r2 = ctypes.windll.user32.SendInput(
                1, ctypes.byref(inp_up), ctypes.sizeof(inp_up)
            )

            if r1 == 0 or r2 == 0:
                log.warning(f"SendInput 点击失败: down={r1}, up={r2}")
                return False
            return True
        except Exception as e:
            log.error(f"鼠标点击异常: {e}")
            return False

    @staticmethod
    def move_and_click(x: int, y: int) -> bool:
        """
        移动鼠标到 (x, y) 并点击。
        这是批量扫描时的核心方法，每次耗时 ~10ms。
        """
        if not MouseController.move_to(x, y):
            return False
        return MouseController.click()

    @staticmethod
    def scroll_one_tick() -> bool:
        """
        滚轮向下滚动 1 格（WHEEL_DELTA = 120）。
        用于精准翻页状态机，每滚一格检查一次颜色变化。
        """
        return MouseController.scroll(-1)

    @staticmethod
    def scroll(clicks: int = 1) -> bool:
        """
        鼠标滚轮滚动。

        参数:
            clicks: 滚动格数，正数向上，负数向下

        返回:
            是否成功
        """
        try:
            inp = INPUT()
            inp.type = INPUT_MOUSE
            inp.mi.dwFlags = MOUSEEVENTF_WHEEL
            inp.mi.mouseData = ctypes.c_ulong(clicks * 120)  # WHEEL_DELTA = 120

            result = ctypes.windll.user32.SendInput(
                1, ctypes.byref(inp), ctypes.sizeof(inp)
            )
            if result == 0:
                log.warning(f"SendInput 滚轮失败: clicks={clicks}")
                return False
            return True
        except Exception as e:
            log.error(f"鼠标滚轮异常: {e}")
            return False

    @staticmethod
    def drag(
        from_x: int,
        from_y: int,
        to_x: int,
        to_y: int,
        steps: int = 10,
        step_delay_ms: int = 10,
    ) -> bool:
        """鼠标左键拖拽：从 (from_x, from_y) 拖到 (to_x, to_y)"""
        try:
            MouseController.move_to(from_x, from_y)
            time.sleep(0.02)

            inp_down = INPUT()
            inp_down.type = INPUT_MOUSE
            inp_down.mi.dwFlags = MOUSEEVENTF_LEFTDOWN
            r = ctypes.windll.user32.SendInput(
                1, ctypes.byref(inp_down), ctypes.sizeof(inp_down)
            )
            if r == 0:
                return False
            time.sleep(0.02)

            for i in range(1, steps + 1):
                x = from_x + (to_x - from_x) * i // steps
                y = from_y + (to_y - from_y) * i // steps
                MouseController.move_to(x, y)
                time.sleep(step_delay_ms / 1000.0)

            time.sleep(0.02)
            inp_up = INPUT()
            inp_up.type = INPUT_MOUSE
            inp_up.mi.dwFlags = MOUSEEVENTF_LEFTUP
            ctypes.windll.user32.SendInput(
                1, ctypes.byref(inp_up), ctypes.sizeof(inp_up)
            )
            return True
        except Exception as e:
            log.error(f"鼠标拖拽异常: {e}")
            return False