"""
通用截图工具类
==============
纯截图模块，不关心"哪个窗口"——窗口查找逻辑已移至 window_helper。
接受 WindowInfo 作为输入，负责将窗口像素转换为 numpy 数组。

依赖（均为项目已有）：
  - pywin32   → PrintWindow 截图
  - pyautogui → 区域截图
  - pillow    → 备用截图
  - opencv + numpy → 图像处理
  - PySide6     → QPixmap 转换（可选，仅在 GUI 中使用时导入）

使用示例:
    from backend.automation.window_helper import WindowHelper
    from backend.utils.screen_capture import ScreenshotCapture, CaptureMethod

    cap = ScreenshotCapture()
    win = WindowHelper.find_genshin_window()
    if win:
        result = cap.capture(window=win)
        result.save("output.png")
"""

from __future__ import annotations

import ctypes
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path

import numpy as np
from utils.datetime_helper import DateTimeHelper

from backend.automation.window_helper import WindowInfo

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
    from PySide6.QtGui import QImage, QPixmap

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
class CaptureResult:
    """截图结果 — 自包含对象，携带像素数据、窗口原点、元信息

    使用示例:
        result = cap.capture(window=win)
        # 坐标转换（窗口相对 → 屏幕绝对）
        screen_x, screen_y = result.to_absolute(100, 200)
        # 窗口原点
        ox, oy = result.window_origin
    """

    image: np.ndarray  # RGB 格式
    method: CaptureMethod
    elapsed_ms: float
    window_left: int = 0  # 截图时的窗口屏幕坐标
    window_top: int = 0
    timestamp: datetime = field(default_factory=DateTimeHelper.now)

    @property
    def width(self) -> int:
        return self.image.shape[1]

    @property
    def height(self) -> int:
        return self.image.shape[0]

    @property
    def shape(self) -> tuple[int, int, int]:
        return self.image.shape

    @property
    def window_origin(self) -> tuple[int, int]:
        """截图时的窗口原点（屏幕坐标）"""
        return (self.window_left, self.window_top)

    def to_absolute(self, x: int, y: int) -> tuple[int, int]:
        """将窗口相对坐标转换为屏幕绝对坐标"""
        return (self.window_left + x, self.window_top + y)

    def __repr__(self) -> str:
        return (
            f"CaptureResult({self.width}x{self.height}, "
            f"method={self.method.name}, {self.elapsed_ms:.1f}ms, "
            f"win@({self.window_left},{self.window_top}))"
        )

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

    def draw_rect(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        color: tuple[int, int, int] = (0, 255, 0),
        thickness: int = 2,
        label: str | None = None,
    ) -> CaptureResult:
        """
        在截图上绘制矩形边框（原地修改）。

        用于 GUI 调试时标记关注区域，如模板匹配位置、OCR 识别区域等。
        支持链式调用。

        参数:
            x, y: 矩形左上角坐标（相对于截图，非屏幕坐标）
            width, height: 矩形宽高
            color: RGB 颜色元组，默认绿色 (0, 255, 0)
            thickness: 线条粗细，默认 2px；设为 -1 则填充矩形
            label: 可选标签文字，绘制在矩形上方

        返回:
            self，支持链式调用

        使用示例:
            result = cap.capture()
            result.draw_rect(100, 200, 50, 50, color=(255, 0, 0), label="背包图标")
            pixmap = result.to_qpixmap()  # 在 GUI 中显示带标记的截图
        """
        import cv2

        bgr_color = (color[2], color[1], color[0])
        img_bgr = cv2.cvtColor(self.image, cv2.COLOR_RGB2BGR)
        cv2.rectangle(img_bgr, (x, y), (x + width, y + height), bgr_color, thickness)
        if label:
            img_bgr = self._draw_label_pil(img_bgr, label, x, y - 6, bgr_color)
        self.image = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        return self

    @staticmethod
    def _draw_label_pil(
        img_bgr: np.ndarray,
        label: str,
        x: int,
        y: int,
        color: tuple[int, int, int],
    ) -> np.ndarray:
        """用 PIL 绘制标签文字（cv2.putText 不支持中文）"""
        import cv2 as _cv2
        from PIL import Image, ImageDraw, ImageFont

        rgb = _cv2.cvtColor(img_bgr, _cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb)
        draw = ImageDraw.Draw(pil_img)

        font = None
        for fp in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf"):
            if Path(fp).exists():
                font = ImageFont.truetype(fp, 18)
                break

        draw.text((x, y), label, font=font, fill=color[::-1])
        return _cv2.cvtColor(np.array(pil_img), _cv2.COLOR_RGB2BGR)

    def draw_rect_safe(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        color: tuple[int, int, int] = (0, 255, 0),
        thickness: int = 2,
        label: str | None = None,
    ) -> CaptureResult:
        """
        在截图上绘制矩形边框（返回新对象，不修改原图）。

        与 draw_rect 功能相同，但会先复制图像再绘制，
        适合需要保留原始截图用于后续匹配的场景。
        """
        import copy

        new_result = copy.copy(self)
        new_result.image = self.image.copy()
        return new_result.draw_rect(x, y, width, height, color, thickness, label)


# ===================== ScreenshotCapture 类 =====================


class ScreenshotCapture:
    """纯截图工具类 — 接受 WindowInfo 作为输入，不自己查找窗口"""

    def __init__(self, default_method: CaptureMethod = CaptureMethod.WIN32):
        self.default_method = default_method

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
            window: 目标窗口（WIN32 方法必须传入）
            region: 截图区域 (left, top, width, height)，用于 pyautogui/pillow

        返回:
            CaptureResult，包含 RGB 格式的 numpy 数组
        """
        method = method or self.default_method
        t0 = time.perf_counter()

        if method == CaptureMethod.WIN32:
            if window is None:
                raise ValueError("WIN32 截图方法必须传入 window 参数")
            img = self._capture_win32(window)
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
        return CaptureResult(
            image=img,
            method=method,
            elapsed_ms=elapsed,
            window_left=window.left if window else 0,
            window_top=window.top if window else 0,
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
    def _capture_win32(window: WindowInfo) -> np.ndarray:
        """pywin32 PrintWindow 截图 → RGB

        直接使用 WindowInfo 中的尺寸，不再重复调用 GetWindowRect，
        确保截图尺寸与窗口查找时的尺寸一致。
        """
        hwnd = window.hwnd
        width = window.width
        height = window.height

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
        except Exception:
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