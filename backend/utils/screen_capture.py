"""
通用截图工具类
==============
支持多种截图后端，可在 PyQt6 GUI 和命令行中复用。

依赖（均为项目已有）：
  - pywin32   → 窗口查找 + PrintWindow 截图
  - pyautogui → 区域截图
  - pillow    → 备用截图
  - opencv + numpy → 图像处理
  - PyQt6     → QPixmap 转换（可选，仅在 GUI 中使用时导入）

使用示例:
    from backend.automation.screen_capture import ScreenshotCapture, CaptureMethod

    cap = ScreenshotCapture()

    # 查找窗口
    win = cap.find_genshin_window()
    if win:
        print(f"找到: {win.title} @ {win.rect}")

    # 截图
    result = cap.capture(method=CaptureMethod.WIN32)
    result.save("output.png")

    # PyQt6 中使用
    pixmap = result.to_qpixmap()
    label.setPixmap(pixmap)
"""

from __future__ import annotations

import ctypes
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path

import numpy as np

# ===================== 可选依赖检测 =====================

_HAS_WIN32 = False
try:
    import win32con
    import win32gui
    import win32ui

    _HAS_WIN32 = True
except ImportError:
    pass

_HAS_PYQT6 = False
try:
    from PyQt6.QtGui import QImage, QPixmap

    _HAS_PYQT6 = True
except ImportError:
    pass


# ===================== 枚举 & 数据类 =====================


class CaptureMethod(Enum):
    """截图方法"""

    WIN32 = auto()
    PYAUTOGUI = auto()
    PILLOW = auto()
    FULLSCREEN = auto()


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


@dataclass
class CaptureResult:
    """截图结果"""

    image: np.ndarray  # RGB 格式
    width: int
    height: int
    method: CaptureMethod
    elapsed_ms: float
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def shape(self) -> tuple[int, int, int]:
        return self.image.shape

    def to_qpixmap(self) -> QPixmap:
        """转换为 QPixmap（PyQt6 GUI 中使用）"""
        if not _HAS_PYQT6:
            raise ImportError("PyQt6 未安装，无法转换为 QPixmap")
        h, w, ch = self.image.shape
        bytes_per_line = ch * w
        qimage = QImage(
            self.image.tobytes(), w, h, bytes_per_line, QImage.Format.Format_RGB888
        )
        return QPixmap.fromImage(qimage.copy())

    def save(self, filepath: str | Path) -> str:
        """保存为 PNG，返回文件路径"""
        import cv2

        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        img_bgr = cv2.cvtColor(self.image, cv2.COLOR_RGB2BGR)
        cv2.imwrite(str(filepath), img_bgr)
        return str(filepath)

    def info(self) -> str:
        """返回简要信息字符串"""
        return (
            f"CaptureResult({self.width}x{self.height}, "
            f"method={self.method.name}, {self.elapsed_ms:.1f}ms)"
        )


# ===================== ScreenshotCapture 类 =====================


class ScreenshotCapture:
    """通用截图工具类"""

    GENSHIN_TITLES = ("原神", "Genshin Impact")
    GENSHIN_CLASS = "UnityWndClass"

    def __init__(self, default_method: CaptureMethod = CaptureMethod.WIN32):
        self.default_method = default_method

    # ---------- 窗口查找 ----------

    @staticmethod
    def find_genshin_window() -> WindowInfo | None:
        """
        查找原神游戏窗口。
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
            if not title:
                return True
            rect = win32gui.GetWindowRect(hwnd)
            w, h = rect[2] - rect[0], rect[3] - rect[1]
            if w < 400 or h < 300:
                return True
            info = WindowInfo(hwnd, title, class_name, *rect)
            if title in ScreenshotCapture.GENSHIN_TITLES:
                exact_matches.append(info)
            if class_name == ScreenshotCapture.GENSHIN_CLASS:
                class_matches.append(info)
            return True

        win32gui.EnumWindows(enum_callback, None)
        return (
            exact_matches[0]
            if exact_matches
            else (class_matches[0] if class_matches else None)
        )

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

    # ---------- 截图入口 ----------

    def capture(
        self,
        method: CaptureMethod | None = None,
        window: WindowInfo | None = None,
        region: tuple[int, int, int, int] | None = None,
    ) -> CaptureResult:
        """
        执行截图。

        参数:
            method: 截图方法，默认使用 WIN32
            window: 目标窗口（WIN32 方法需要）
            region: 截图区域 (left, top, width, height)，用于 pyautogui/pillow

        返回:
            CaptureResult，包含 RGB 格式的 numpy 数组
        """
        method = method or self.default_method
        t0 = time.perf_counter()

        if method == CaptureMethod.WIN32:
            if window is None:
                window = self.find_genshin_window()
            if window is None:
                raise RuntimeError("未找到原神窗口，无法使用 WIN32 方法截图")
            img = self._capture_win32(window.hwnd)
        elif method == CaptureMethod.PYAUTOGUI:
            r = region or (0, 0, 1920, 1080)
            img = self._capture_pyautogui(*r)
        elif method == CaptureMethod.PILLOW:
            r = region or (0, 0, 1920, 1080)
            img = self._capture_pillow(*r)
        elif method == CaptureMethod.FULLSCREEN:
            img = self._capture_fullscreen()
        else:
            raise ValueError(f"不支持的截图方法: {method}")

        elapsed = (time.perf_counter() - t0) * 1000
        h, w = img.shape[:2]
        return CaptureResult(
            image=img, width=w, height=h, method=method, elapsed_ms=elapsed
        )

    def capture_window(
        self, window: WindowInfo, method: CaptureMethod = CaptureMethod.WIN32
    ) -> CaptureResult:
        """截取指定窗口"""
        return self.capture(
            method=method,
            window=window,
            region=(window.left, window.top, window.width, window.height),
        )

    # ---------- 内部实现 ----------

    @staticmethod
    def _capture_win32(hwnd: int) -> np.ndarray:
        """pywin32 PrintWindow 截图 → RGB"""
        rect = win32gui.GetWindowRect(hwnd)
        width = rect[2] - rect[0]
        height = rect[3] - rect[1]

        hwnd_dc = win32gui.GetWindowDC(hwnd)
        mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
        save_dc = mfc_dc.CreateCompatibleDC()

        bitmap = win32ui.CreateBitmap()
        bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
        save_dc.SelectObject(bitmap)

        try:
            result = ctypes.windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), 2)
            if result == 0:
                save_dc.BitBlt(
                    (0, 0), (width, height), mfc_dc, (0, 0), win32con.SRCCOPY
                )
        except Exception:  # noqa: BLE001
            save_dc.BitBlt((0, 0), (width, height), mfc_dc, (0, 0), win32con.SRCCOPY)

        bitmap_bits = bitmap.GetBitmapBits(True)
        img = np.frombuffer(bitmap_bits, dtype=np.uint8).reshape((height, width, 4))

        win32gui.DeleteObject(bitmap.GetHandle())
        save_dc.DeleteDC()
        mfc_dc.DeleteDC()
        win32gui.ReleaseDC(hwnd, hwnd_dc)

        return img[:, :, [2, 1, 0]]  # BGRA → RGB

    @staticmethod
    def _capture_pyautogui(left: int, top: int, width: int, height: int) -> np.ndarray:
        """pyautogui 区域截图 → RGB"""
        import pyautogui

        img = pyautogui.screenshot(region=(left, top, width, height))
        return np.array(img)

    @staticmethod
    def _capture_pillow(left: int, top: int, width: int, height: int) -> np.ndarray:
        """PIL 区域截图 → RGB"""
        from PIL import ImageGrab

        img = ImageGrab.grab(
            bbox=(left, top, left + width, top + height), all_screens=True
        )
        return np.array(img)

    @staticmethod
    def _capture_fullscreen() -> np.ndarray:
        """全屏截图 → RGB"""
        try:
            import pyautogui

            return np.array(pyautogui.screenshot())
        except ImportError:
            from PIL import ImageGrab

            return np.array(ImageGrab.grab(all_screens=True))

    # ---------- 静态工具方法 ----------

    @staticmethod
    def numpy_to_qpixmap(img: np.ndarray) -> QPixmap:
        """numpy RGB 数组 → QPixmap"""
        if not _HAS_PYQT6:
            raise ImportError("PyQt6 未安装")
        h, w, ch = img.shape
        bytes_per_line = ch * w
        qimage = QImage(img.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        return QPixmap.fromImage(qimage.copy())

    @staticmethod
    def qpixmap_to_numpy(pixmap: QPixmap) -> np.ndarray:
        """QPixmap → numpy RGB 数组"""
        if not _HAS_PYQT6:
            raise ImportError("PyQt6 未安装")
        qimage = pixmap.toImage().convertToFormat(QImage.Format.Format_RGB888)
        width, height = qimage.width(), qimage.height()
        ptr = qimage.bits()
        ptr.setsize(height * width * 3)
        return np.array(ptr).reshape((height, width, 3)).copy()