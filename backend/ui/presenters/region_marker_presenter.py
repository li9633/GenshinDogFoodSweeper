"""区域标记 Presenter — QObject 封装，供 QML 绑定

通过 Signal/Slot/Property 暴露给 QML，内部委托给纯业务方法。
"""

from __future__ import annotations

import time

import cv2
import numpy as np
from PySide6.QtCore import Property, QObject, Signal, Slot
from PySide6.QtWidgets import QApplication
from utils.logger import log

from backend.automation.color_sampler import sample_roi_color
from backend.automation.template_manager import TemplateManager
from backend.automation.window_helper import WindowHelper
from backend.utils.screen_capture import CaptureResult, ScreenshotCapture

from .image_provider import PreviewImageProvider


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
    markingChanged = Signal()
    extractingChanged = Signal()


    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._x = 0
        self._y = 0
        self._w = 100
        self._h = 100
        self._selection_mode = False
        self._marking = False
        self._extracting = False
        self._last_capture: CaptureResult | None = None

    @Property(bool, notify=markingChanged)
    def marking(self) -> bool:
        return self._marking

    @Property(bool, notify=extractingChanged)
    def extracting(self) -> bool:
        return self._extracting

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
        log.debug(f"setCoords called: ({x}, {y}, {w}, {h})  current: ({self._x}, {self._y}, {self._w}, {self._h})")
        if (x, y, w, h) == (self._x, self._y, self._w, self._h):
            log.debug("setCoords: values unchanged, skipping")
            return
        self._x = x
        self._y = y
        self._w = w
        self._h = h
        self.coordsChanged.emit()
        log.debug(f"setCoords: updated to ({self._x}, {self._y}, {self._w}, {self._h}), coordsChanged emitted")

    @Property(str)
    def coordsText(self) -> str:
        return f"{self._x},{self._y},{self._w},{self._h}"

    # ========== 业务 Slots ==========

    @Slot()
    def mark(self) -> None:
        """截图并标记区域"""
        self._marking = True
        self.markingChanged.emit()
        try:
            t0 = time.perf_counter()
            result = _capture()
            self._last_capture = result
            marked = _mark_region(result, self._x, self._y, self._w, self._h)
            key = PreviewImageProvider.put("region", marked.image)
            self.captureFinished.emit(key, self._x, self._y, self._w, self._h)
            elapsed = (time.perf_counter() - t0) * 1000
            log.info(f"区域标记完成 ({elapsed:.0f}ms)")
        finally:
            self._marking = False
            self.markingChanged.emit()

    @Slot(str)
    def saveTemplate(self, filename: str) -> None:
        """保存当前区域为模板"""
        if not filename.strip():
            self.errorOccurred.emit("请输入文件名")
            return
        t0 = time.perf_counter()
        result = _capture()
        _save_template(result, filename.strip(), self._x, self._y, self._w, self._h)
        self.templateSaved.emit(filename.strip())
        elapsed = (time.perf_counter() - t0) * 1000
        log.info(f"模板保存完成 ({elapsed:.0f}ms)")

    @Slot()
    def extractColor(self) -> None:
        """提取区域主色调"""
        self._extracting = True
        self.extractingChanged.emit()
        try:
            t0 = time.perf_counter()
            result = _capture()
            self._last_capture = result
            c = _extract_color(result, self._x, self._y, self._w, self._h)
            self.colorExtracted.emit(c["r"], c["g"], c["b"], c["h_hsv"], c["s_hsv"], c["v_hsv"])
            self.colorExtractedString.emit(
                f"RGB({c['r']}, {c['g']}, {c['b']})  "
                f"HSV({c['h_hsv']}°, {c['s_hsv'] / 255:.0%}, {c['v_hsv'] / 255:.0%})"
            )
            elapsed = (time.perf_counter() - t0) * 1000
            log.info(f"颜色提取完成 ({elapsed:.0f}ms)")
        finally:
            self._extracting = False
            self.extractingChanged.emit()

    @Slot()
    def copyCoords(self) -> None:
        """复制坐标到剪贴板"""
        text = self.coordsText
        QApplication.clipboard().setText(text)
        log.info(f"已复制坐标到剪贴板: {text}")

    @Slot()
    def pasteCoords(self) -> None:
        """从剪贴板导入坐标（格式: x,y,w,h）"""
        raw = QApplication.clipboard().text().strip()
        if not raw:
            self.errorOccurred.emit("剪贴板为空")
            return
        parts = raw.split(",")
        if len(parts) < 4:
            self.errorOccurred.emit(f"剪贴板格式无效: {raw}（需要 x,y,w,h）")
            return
        try:
            x = int(parts[0].strip())
            y = int(parts[1].strip())
            w = int(parts[2].strip())
            h = int(parts[3].strip())
            self.setCoords(x, y, w, h)
            log.info(f"已从剪贴板导入坐标: {self.coordsText}")
        except ValueError:
            self.errorOccurred.emit(f"剪贴板坐标解析失败: {raw}")

    @Slot()
    def clear(self) -> None:
        """清除预览"""
        self._last_capture = None
        PreviewImageProvider.clear("region")
        self.clearPreview.emit()


# ========== 纯业务方法（保留原有静态方法兼容性） ==========

def _capture() -> CaptureResult:
    window = WindowHelper.find_genshin_window()
    return ScreenshotCapture().capture(window=window)


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
    # cv2.imwrite 不支持中文路径，改用 imencode + 二进制写入
    success, buf = cv2.imencode(".png", cv2.cvtColor(roi, cv2.COLOR_RGB2BGR))
    if success:
        save_path.write_bytes(buf.tobytes())
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