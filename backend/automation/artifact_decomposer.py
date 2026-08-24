"""自动分解低星圣遗物模块"""

from __future__ import annotations

import time

import numpy as np
from PySide6.QtCore import QEventLoop, QObject
from utils.logger import log

from backend.automation.mouse_controller import MouseController
from backend.automation.template_manager import TemplateManager
from backend.automation.template_matcher import multi_scale_match
from backend.automation.window_helper import WindowHelper
from backend.utils.screen_capture import ScreenshotCapture


class ArtifactDecomposer(QObject):
    """自动分解4星及以下圣遗物"""

    # 模板匹配阈值
    MATCH_THRESHOLD = 0.80

    def __init__(self) -> None:
        super().__init__()
        self._capture = ScreenshotCapture()
        self._window = WindowHelper()
        self._quick_select_pos: tuple[int, int] | None = None  # 屏幕绝对坐标

    # ========== 入口 ==========

    def run(self) -> bool:
        """
        主入口：确保当前在分解页面，然后执行分解逻辑。

        Returns:
            True 成功进入分解页面，False 失败
        """
        log.info("开始自动分解流程")

        # 聚焦原神窗口
        if not self._window.focus():
            log.error("聚焦原神窗口失败")
            return False

        # 1. 截图
        result = self._capture.capture()
        if result is None:
            log.error("截图失败")
            return False

        # 2. 如果不在分解页面，则尝试进入
        if not self._is_on_decompose_page(result.image):
            log.info("未在分解页面，尝试查找分解按钮")
            if not self._click_decompose_button(result.image):
                log.error("未找到分解按钮")
                return False
            time.sleep(1.5)
            result2 = self._capture.capture()
            if result2 is None:
                log.error("点击分解按钮后截图失败")
                return False
            if not self._is_on_decompose_page(result2.image):
                log.error("点击分解按钮后未能进入分解页面")
                return False
        else:
            log.info("已在分解页面")

        log.info("已进入分解页面，开始执行分解操作")

        # 3. 点击快速选择按钮
        time.sleep(0.5)
        result3 = self._capture.capture()
        if result3 is None:
            log.error("快速选择前截图失败")
            return False
        if not self._click_quick_select(result3.image):
            log.error("未找到快速选择按钮")
            return False
        log.info("已点击快速选择，开始 OCR 识别")

        # 4. 截图并 OCR 识别快速选择弹窗内容
        time.sleep(0.5)
        result4 = self._capture.capture()
        if result4 is None:
            log.error("OCR 截图失败")
            return False
        ocr_result = self._ocr_quick_select(result4.image)
        if ocr_result is None:
            log.error("OCR 识别失败")
            return False
        log.info(f"OCR 识别完成: {len(ocr_result)} 个区域")
        # 解析快速选择结果
        options = ArtifactDecomposer._parse_quick_select_result(
            ocr_result, roi_offset=(self.QUICK_SELECT_ROI[0], self.QUICK_SELECT_ROI[1])
        )
        for opt in options:
            log.debug(
                f"  {opt['star']}星圣遗物 ×{opt['count']} "
                f"位置(窗口相对)=({opt['pos'][0]}, {opt['pos'][1]})"
            )
        if not options:
            log.warning("未解析到任何快速选择选项")
            return False

        # 5. 关闭快速选择弹窗
        if self._quick_select_pos is None:
            log.error("快速选择按钮坐标丢失，无法关闭弹窗")
            return False
        MouseController.move_and_click(*self._quick_select_pos)
        log.info("已关闭快速选择弹窗")

        # 6. 根据数量决定是否分解
        has_any = any(opt["count"] > 0 for opt in options)
        if not has_any:
            log.info("所有星级圣遗物数量均为0，暂无需要分解的圣遗物")
            return True

        log.info("存在可分解圣遗物，开始执行分解")
        time.sleep(0.5)
        result5 = self._capture.capture()
        if result5 is None:
            log.error("分解前截图失败")
            return False
        if not self._click_decompose_button(result5.image):
            log.error("未找到分解按钮")
            return False
        log.info("已点击分解按钮")
        return True

    # ========== 模板检测 ==========

    def _is_on_decompose_page(self, image: np.ndarray) -> bool:
        """通过模板匹配判断当前是否在分解页面"""
        template = TemplateManager.get("圣遗物分解文本")
        if template is None:
            log.error("未找到模板: 圣遗物分解文本")
            return False
        return self._match_template(image, template, self.MATCH_THRESHOLD)

    def _click_decompose_button(self, image: np.ndarray) -> bool:
        """查找并点击分解按钮"""
        template = TemplateManager.get("圣遗物分解页面分解按钮")
        if template is None:
            log.error("未找到模板: 圣遗物分解页面分解按钮")
            return False
        return self._match_and_click(image, template, "圣遗物分解页面分解按钮")

    # ========== 快速选择 ==========

    def _click_quick_select(self, image: np.ndarray) -> bool:
        """查找并点击快速选择按钮，成功后保存坐标供后续复用"""
        template = TemplateManager.get("快速选择按钮")
        if template is None:
            log.error("未找到模板: 快速选择按钮")
            return False
        pos = self._match_and_click_return_pos(image, template, "快速选择按钮")
        if pos is None:
            return False
        self._quick_select_pos = pos
        return True

    # ========== OCR 任务工厂 ==========

    # 快速选择弹窗的 OCR 识别区域 (x, y, w, h)
    QUICK_SELECT_ROI = (23, 114, 639, 360)

    @staticmethod
    def create_quick_select_ocr_task(
        image: np.ndarray,
    ):
        """创建快速选择弹窗的 OCR 识别任务。

        返回一个 callable(ocr_instance)，可在 OcrWorker 线程中执行。
        使用方式:
            worker = OcrWorker.instance()
            worker.submit(
                ArtifactDecomposer.create_quick_select_ocr_task(image),
                callback_data="quick_select",
            )
        """
        rx, ry, rw, rh = ArtifactDecomposer.QUICK_SELECT_ROI
        roi = image[ry:ry + rh, rx:rx + rw]

        def task(ocr) -> list:
            result = ocr.ocr(roi)
            count = len(result) if result is not None and len(result) > 0 else 0
            log.debug(f"[快速选择OCR] 识别到 {count} 个文本区域")
            return result

        return task

    # ========== OCR 执行 ==========

    def _ocr_quick_select(self, image: np.ndarray) -> list | None:
        """通过 OcrWorker 同步执行 OCR 识别快速选择弹窗内容。

        使用 QEventLoop 等待 OcrWorker 异步结果，
        不阻塞主线程事件循环，确保跨线程信号可正常投递。
        """
        from backend.automation.ocr_worker import OcrWorker

        result_holder: list = []
        loop = QEventLoop()

        def on_done(result, _cb):
            result_holder.append(result)
            loop.quit()

        def on_error(err, _cb):
            log.error(f"[快速选择OCR] 失败: {err}")
            loop.quit()

        worker = OcrWorker.instance()
        worker.task_done.connect(on_done)
        worker.task_error.connect(on_error)

        task = ArtifactDecomposer.create_quick_select_ocr_task(image)
        worker.submit(task, callback_data="quick_select")

        # QEventLoop 处理事件循环，不阻塞信号投递
        loop.exec()

        try:
            worker.task_done.disconnect(on_done)
            worker.task_error.disconnect(on_error)
        except Exception:
            log.debug("断开 OCR 信号连接时发生异常", exc_info=True)

        return result_holder[0] if result_holder else None

    # ========== 快速选择结果解析 ==========

    @staticmethod
    def _parse_quick_select_result(
        ocr_result: list,
        roi_offset: tuple[int, int] = (0, 0),
    ) -> list[dict]:
        """解析快速选择弹窗 OCR 结果，返回结构化选项列表。

        OCR 识别到的文本按「星级标签 → 数量」交替排列，如：
        "1星圣遗物" → "1" → "2星圣遗物" → "4" → ...

        Args:
            ocr_result: ocr.ocr() 原始返回值 [[page0], ...]
            roi_offset: ROI 在窗口中的偏移 (x, y)，用于计算窗口相对坐标

        Returns:
            [{"star": 1, "label": "1星圣遗物", "count": 4, "pos": (x, y)}, ...]
        """
        import re

        lines: list[dict] = []

        if ocr_result is None:
            return []
        if not isinstance(ocr_result, (list, tuple)) or len(ocr_result) == 0:
            return []

        page = ocr_result[0]
        if page is None:
            return []
        # 避免 numpy 数组直接做布尔判断
        if hasattr(page, "__len__") and len(page) == 0:
            return []

        if isinstance(page, dict):
            rec_texts = page.get("rec_texts", [])
            dt_polys = page.get("dt_polys", [])
            for text, poly in zip(rec_texts, dt_polys):
                if not text or not text.strip():
                    continue
                cx = sum(p[0] for p in poly) / len(poly) if poly is not None and len(poly) > 0 else 0
                cy = sum(p[1] for p in poly) / len(poly) if poly is not None and len(poly) > 0 else 0
                lines.append({"text": text.strip(), "cx": cx, "cy": cy})
        elif isinstance(page, list):
            for line_info in page:
                if not isinstance(line_info, (list, tuple)) or len(line_info) < 2:
                    continue
                poly = line_info[0]
                rec = line_info[1]
                text = rec[0] if isinstance(rec, (list, tuple)) else str(rec)
                if not text or not text.strip():
                    continue
                if poly is not None and len(poly) > 0:
                    cx = sum(p[0] for p in poly) / len(poly)
                    cy = sum(p[1] for p in poly) / len(poly)
                else:
                    cx, cy = 0, 0
                lines.append({"text": text.strip(), "cx": cx, "cy": cy})

        # 按 Y 坐标从上到下排序
        lines.sort(key=lambda l: l["cy"])

        rx, ry = roi_offset
        options: list[dict] = []
        i = 0
        while i < len(lines) - 1:
            label_line = lines[i]
            count_line = lines[i + 1]

            # 标签行包含「星圣遗物」
            if "星圣遗物" in label_line["text"]:
                star_m = re.search(r"(\d+)\s*星", label_line["text"])
                # 数量：提取所有数字字符，兼容 1000 / 1,000 / 1, 000 / 1.000 等格式
                count_clean = re.sub(r"[^\d]", "", count_line["text"])
                try:
                    count = int(count_clean)
                except ValueError:
                    count = None

                if star_m and count is not None:
                    star = int(star_m.group(1))
                    wx = int(rx + label_line["cx"])
                    wy = int(ry + label_line["cy"])
                    options.append({
                        "star": star,
                        "label": label_line["text"],
                        "count": count,
                        "pos": (wx, wy),
                    })
                    i += 2
                    continue
            i += 1

        return options

    # ========== 底层工具 ==========

    def _match_template(
        self, image: np.ndarray, template: object, threshold: float
    ) -> bool:
        """模板匹配，返回是否匹配成功"""
        gray = np.dot(image[..., :3], [0.299, 0.587, 0.114]).astype(np.uint8)
        score, loc, scale, size = multi_scale_match(gray, template)
        log.debug(
            f"[_match_template] 得分={score:.3f} 阈值={threshold:.3f} "
            f"位置(窗口相对)={loc} 缩放={scale:.2f} 模板尺寸={size}"
        )
        return score >= threshold

    def _match_and_click_return_pos(
        self, image: np.ndarray, template: object, name: str
    ) -> tuple[int, int] | None:
        """模板匹配成功后点击中心位置，返回屏幕绝对坐标。

        与 _match_and_click 逻辑相同，但额外返回点击坐标，
        供后续复用（如快速选择按钮的二次点击）。
        """
        gray = np.dot(image[..., :3], [0.299, 0.587, 0.114]).astype(np.uint8)
        score, loc, scale, size = multi_scale_match(gray, template)
        if score < self.MATCH_THRESHOLD:
            log.warning(
                f"[{name}] 匹配失败: 得分={score:.3f} < 阈值={self.MATCH_THRESHOLD}"
            )
            return None
        tw, th = size
        rel_x = loc[0] + tw // 2
        rel_y = loc[1] + th // 2
        abs_x, abs_y = self._window.to_absolute(rel_x, rel_y)
        win_origin = self._window.get_origin()
        log.info(
            f"[{name}] 匹配成功: 得分={score:.3f} 缩放={scale:.2f} "
            f"窗口相对=({rel_x}, {rel_y}) 窗口原点={win_origin} "
            f"屏幕绝对=({abs_x}, {abs_y})"
        )
        MouseController.move_and_click(abs_x, abs_y)
        return (abs_x, abs_y)