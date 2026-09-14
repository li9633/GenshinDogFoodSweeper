"""调试预览生成器 — 灰度截图转换、滑块调试预览图生成"""

from __future__ import annotations

import cv2
import numpy as np

from backend.automation.slider_detector import SliderDetector


class DebugPreview:
    """调试预览生成器"""

    @staticmethod
    def generate_grayscale(image: np.ndarray) -> np.ndarray:
        """将 BGR 图像转换为灰度预览图"""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        debug = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        return cv2.cvtColor(debug, cv2.COLOR_BGR2RGB)

    @staticmethod
    def generate_slider_debug(
        img: np.ndarray,
        region_x: int,
        top_y: int,
        bottom_y: int,
        region_w: int,
        region_h: int,
        slider_y: int | None,
        label: str = "",
        best_ratio: float = 0.0,
        best_y: int = -1,
    ) -> np.ndarray:
        """生成滑块检测调试预览图（RGB 格式）。

        Args:
            img: 原始截图（BGR 格式）
            region_x, top_y, bottom_y, region_w, region_h: 检测区域参数
            slider_y: 检测到的滑块Y坐标
            label: 调试标签
            best_ratio: 最佳匹配率
            best_y: 最佳匹配Y坐标

        Returns:
            RGB 格式的调试预览图
        """
        debug = SliderDetector.generate_debug_preview(
            img, region_x, top_y, bottom_y,
            region_w, region_h, slider_y, label, best_ratio, best_y,
        )
        return cv2.cvtColor(debug, cv2.COLOR_BGR2RGB)