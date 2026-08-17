"""预览图 Provider — QQuickImageProvider 内存缓存，零 IO

用法：
  Presenter: PreviewImageProvider.put("region", numpy_rgb_array)
  QML:       Image { source: "image://preview/region" }
"""

from __future__ import annotations

import numpy as np
from PySide6.QtGui import QImage
from PySide6.QtQuick import QQuickImageProvider
from utils.logger import log


class PreviewImageProvider(QQuickImageProvider):
    """内存中缓存预览图，QML 通过 image://preview/<key> 访问"""

    _instance: PreviewImageProvider | None = None

    def __init__(self) -> None:
        super().__init__(QQuickImageProvider.Image)
        self._images: dict[str, QImage] = {}
        self._counter: int = 0
        PreviewImageProvider._instance = self

    @staticmethod
    def put(key: str, rgb: np.ndarray) -> str:
        """存入 numpy RGB 数组，返回带版本号的 key（用于 QML URL 缓存刷新）。

        Presenter 应将返回值通过信号传给 QML，而非直接使用原始 key。
        """
        inst = PreviewImageProvider._instance
        if inst is None:
            log.warning(f"[ImageProvider] put({key}) 失败: _instance is None")
            return key
        rgb = np.ascontiguousarray(rgb)
        h, w, ch = rgb.shape
        qimg = QImage(rgb.tobytes(), w, h, ch * w, QImage.Format.Format_RGB888)
        inst._images[key] = qimg.copy()
        inst._counter += 1
        return f"{key}?v={inst._counter}"

    @staticmethod
    def clear(key: str | None = None) -> None:
        """清除缓存。key=None 时清除全部"""
        inst = PreviewImageProvider._instance
        if inst is None:
            return
        if key is None:
            inst._images.clear()
        else:
            inst._images.pop(key, None)

    def requestImage(self, id: str, requestedSize, *args) -> QImage:
        # 去掉版本后缀 "?v=N"，用原始 key 查找
        base_key = id.split("?")[0]
        return self._images.get(base_key, QImage())