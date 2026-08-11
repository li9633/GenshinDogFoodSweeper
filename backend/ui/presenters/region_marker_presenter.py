"""区域标记 Presenter — QObject 封装，供 QML 绑定

通过 Signal/Slot/Property 暴露给 QML，内部委托给纯业务方法。
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import cv2
import numpy as np
from PySide6.QtCore import Property, QObject, Signal, Slot
from .image_provider import PreviewImageProvider
from utils.logger import log

from backend.automation.color_sampler import sample_roi_color
from backend.automation.template_manager import TemplateManager
from backend.utils.screen_capture import CaptureResult, ScreenshotCapture


class RegionMarkerPresenter(QObject):
    """区域标记 Presenter — QML 可绑定"""

    # -- 信号 --
    captureFinished = Signal(str, int, int, int, int)  # path, x, y, w, h
    colorExtracted = Signal(int, int, int, int, int, int)  # r, g, b, h, s, v
    colorExtractedString = Signal(str)  # "RGB(x,x,x) HSV(x,x,x)"
    templateSaved = Signal(str)  # filename
    errorOccurred = Signal(str)
    coordsChanged = Signal()
    selectionModeChanged = Signal()
    clearPreview = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._x = 0
        self._y = 0
        self._w = 100
        self._h = 100
        self._selection_mode = False
        self._last_capture: CaptureResult | None = None

    @Property(bool, notify=selectionModeChanged)
    def selectionMode(self) -> bool:
        return self._selection_mode

    @selectionMode.setter
    def selectionMode(self, val: bool) -> None:
        if self._selection_mode != val:
            self._selection_mode = val
            self.selectionModeChanged.emit()

    # ========== 坐标 Properties ==========

    @Property(int, notify=coordsChanged)
    def regionX(self) -> int:
        return self._x

    @regionX.setter
    def regionX(self, val: int) -> None:
        if self._x != val:
            self._x = val
            self.coordsChanged.emit()

    @Property(int, notify=coordsChanged)
    def regionY(self) -> int:
        return self._y

    @regionY.setter
    def regionY(self, val: int) -> None:
        if self._y != val:
            self._y = val
            self.coordsChanged.emit()

    @Property(int, notify=coordsChanged)
    def regionW(self) -> int:
        return self._w

    @regionW.setter
    def regionW(self, val: int) -> None:
        if self._w != val:
            self._w = val
            self.coordsChanged.emit()

    @Property(int, notify=coordsChanged)
    def regionH(self) -> int:
        return self._h

    @regionH.setter
    def regionH(self, val: int) -> None:
        if self._h != val:
            self._h = val
            self.coordsChanged.emit()

    @Slot(int, int, int, int)
    def setCoords(self, x: int, y: int, w: int, h: int) -> None:
        self._x = x
        self._y = y
        self._w = w
        self._h = h
        self.coordsChanged.emit()

    @Property(str)
    def coordsText(self) -> str:
        return f"{self._x},{self._y},{self._w},{self._h}"

    # ========== 业务 Slots ==========

    @Slot()
    def mark(self) -> None:
        """截图并标记区域"""
        try:
            result = _capture()
            self._last_capture = result
            marked = _mark_region(result, self._x, self._y, self._w, self._h)
            PreviewImageProvider.put("region", marked.image)
            self.captureFinished.emit("region", self._x, self._y, self._w, self._h)
            log.info(f"已标记区域 ({self._x}, {self._y}, {self._w}x{self._h})")
        except Exception as exc:
            self.errorOccurred.emit(str(exc))
            log.error(f"截图失败: {exc}")

    @Slot(str)
    def saveTemplate(self, filename: str) -> None:
        """保存当前区域为模板"""
        if not filename.strip():
            self.errorOccurred.emit("请输入文件名")
            return
        try:
            result = self._last_capture if self._last_capture else _capture()
            _save_template(result, filename.strip(), self._x, self._y, self._w, self._h)
            self.templateSaved.emit(filename.strip())
        except Exception as exc:
            self.errorOccurred.emit(str(exc))
            log.error(f"保存模板失败: {exc}")

    @Slot()
    def extractColor(self) -> None:
        """提取区域主色调"""
        try:
            result = _capture()
            self._last_capture = result
            c = _extract_color(result, self._x, self._y, self._w, self._h)
            self.colorExtracted.emit(c["r"], c["g"], c["b"], c["h_hsv"], c["s_hsv"], c["v_hsv"])
            self.colorExtractedString.emit(
                f"RGB({c['r']}, {c['g']}, {c['b']})  "
                f"HSV({c['h_hsv']}°, {c['s_hsv'] / 255:.0%}, {c['v_hsv'] / 255:.0%})"
            )
            log.info(
                f"颜色提取: RGB({c['r']},{c['g']},{c['b']}) "
                f"HSV({c['h_hsv']},{c['s_hsv']},{c['v_hsv']})"
            )
        except Exception as exc:
            self.errorOccurred.emit(str(exc))
            log.error(f"颜色提取失败: {exc}")

    @Slot()
    def copyCoords(self) -> None:
        """复制坐标到剪贴板（通过 QML 端 Clipboard 处理）"""
        pass

    @Slot()
    def clear(self) -> None:
        """清除预览"""
        self._last_capture = None
        PreviewImageProvider.clear("region")
        self.clearPreview.emit()


# ========== 纯业务方法（保留原有静态方法兼容性） ==========

def _capture() -> CaptureResult:
    return ScreenshotCapture().capture()


def _mark_region(
    result: CaptureResult, x: int, y: int, w: int, h: int
) -> CaptureResult:
    result.draw_rect(
        x, y, w, h, color=(0, 255, 0), thickness=3, label=f"({x}, {y}) {w}x{h}"
    )
    return result


def _save_template(
    result: CaptureResult, filename: str, x: int, y: int, w: int, h: int
) -> None:
    roi = result.image[y : y + h, x : x + w]
    save_dir = TemplateManager.IMAGES_DIR
    save_dir.mkdir(parents=True, exist_ok=True)
    save_path = save_dir / f"{filename}.png"
    cv2.imwrite(str(save_path), cv2.cvtColor(roi, cv2.COLOR_RGB2BGR))
    TemplateManager.register(filename, f"images/{filename}.png", (x, y, w, h))
    TemplateManager.save()
    log.info(f"已保存模板: {filename}.png ({w}x{h})，区域已写入 templates.json")


def _extract_color(result: CaptureResult, x: int, y: int, w: int, h: int) -> dict:
    """提取 ROI 主色调"""
    r, g, b = sample_roi_color(result.image, x, y, w, h)
    hsv = cv2.cvtColor(np.uint8([[[r, g, b]]]), cv2.COLOR_RGB2HSV)[0][0]
    return {
        "r": int(r),
        "g": int(g),
        "b": int(b),
        "h_hsv": int(hsv[0]),
        "s_hsv": int(hsv[1]),
        "v_hsv": int(hsv[2]),
    }


def _save_to_temp(result: CaptureResult) -> str:
    """将截图保存为临时 PNG 文件，返回文件路径（供 QML Image 使用）"""
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    img_bgr = cv2.cvtColor(result.image, cv2.COLOR_RGB2BGR)
    cv2.imwrite(tmp.name, img_bgr)
    return str(Path(tmp.name).as_posix())