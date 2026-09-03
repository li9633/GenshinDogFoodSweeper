"""自动分解低星圣遗物模块"""

from __future__ import annotations

import threading
import time

import numpy as np
from PySide6.QtCore import QEventLoop, QObject, QTimer
from utils.logger import log

from backend.automation.mouse_controller import MouseController
from backend.automation.slot_iterator import SlotIterator
from backend.automation.template_manager import TemplateManager
from backend.automation.template_matcher import multi_scale_match
from backend.automation.window_helper import WindowHelper
from backend.utils.screen_capture import ScreenshotCapture


class ArtifactDecomposer(QObject):
    """自动分解4星及以下圣遗物"""

    # 模板匹配阈值
    MATCH_THRESHOLD = 0.80

    # 快速选择弹窗的 OCR 识别区域 (x, y, w, h)
    QUICK_SELECT_ROI = (23, 114, 639, 360)

    def __init__(self) -> None:
        super().__init__()
        self._capture = ScreenshotCapture()
        self._quick_select_pos: tuple[int, int] | None = None  # 窗口相对坐标
        self._decompose_button_pos: tuple[int, int] | None = None  # 窗口相对坐标
        self._stop_event = threading.Event()
        self._fatal_error: str | None = None  # 致命错误信息，非空时表示发生不可恢复的错误

    def stop(self) -> None:
        """线程安全：设置停止标志，终止正在运行的分解循环。"""
        self._stop_event.set()
        log.info("[ArtifactDecomposer] 停止标志已设置")

    def reset_stop(self) -> None:
        """清除停止标志和致命错误，允许下次运行。"""
        self._stop_event.clear()
        self._fatal_error = None

    # ========== 入口 ==========

    def try_quick_select_decompose(self) -> bool:
        """
        尝试快速选择4星及以下圣遗物并分解。

        前提：调用方已确保当前在分解页面（已调用 enter_decompose_page()）。

        流程：点击快速选择 → OCR识别弹窗 → 有4星及以下圣遗物则分解。

        Returns:
            True 已执行快速分解，False 无4星及以下圣遗物（需进入主流程）
        """
        log.info("尝试快速选择4星及以下圣遗物...")

        # 1. 点击快速选择按钮
        time.sleep(0.5)
        window = WindowHelper.find_genshin_window()
        result = self._capture.capture(window=window)

        if not self._click_quick_select(result.image):
            log.warning("未找到快速选择按钮，跳过快速选择")
            return False

        # 2. 截图并 OCR 识别快速选择弹窗内容
        time.sleep(0.5)
        result2 = self._capture.capture(window=window)

        ocr_result = self._ocr_quick_select(result2.image)
        if ocr_result is None:
            log.warning("快速选择 OCR 识别失败，跳过快速选择")
            # 尝试关闭弹窗
            if self._quick_select_pos:
                MouseController.move_and_click(*self._quick_select_pos)
                time.sleep(0.3)
            return False

        log.info(f"快速选择 OCR 识别完成: {len(ocr_result)} 个区域")

        # 3. 解析快速选择结果
        options = ArtifactDecomposer._parse_quick_select_result(
            ocr_result, roi_offset=(self.QUICK_SELECT_ROI[0], self.QUICK_SELECT_ROI[1])
        )
        for opt in options:
            log.debug(
                f"  {opt['star']}星圣遗物 ×{opt['count']} "
                f"位置(窗口相对)=({opt['pos'][0]}, {opt['pos'][1]})"
            )

        # 4. 检查是否有4星及以下圣遗物
        low_star_options = [opt for opt in options if opt["star"] <= 4]
        has_any = any(opt["count"] > 0 for opt in low_star_options)

        if not has_any:
            log.info("无4星及以下圣遗物，关闭快速选择弹窗，进入主流程")
            if self._quick_select_pos:
                MouseController.move_and_click(*self._quick_select_pos)
                time.sleep(0.3)
            return False

        # 5. 有4星及以下圣遗物，关闭弹窗并执行分解
        log.info(
            f"发现4星及以下圣遗物: "
            f"{[f'{opt["star"]}星×{opt["count"]}' for opt in low_star_options if opt['count'] > 0]}"
        )

        if self._quick_select_pos is None:
            log.error("快速选择按钮坐标丢失，无法关闭弹窗")
            return False
        MouseController.move_and_click(*self._quick_select_pos)
        log.info("已关闭快速选择弹窗")

        time.sleep(0.5)
        result3 = self._capture.capture(window=window)

        if not self._click_decompose_button(result3.image):
            log.error("未找到分解按钮")
            return False

        # 等待确认弹窗出现
        time.sleep(0.3)
        result4 = self._capture.capture(window=window)
        confirm_pos = self._click_confirm_decompose_button(result4.image)
        if confirm_pos is None:
            log.error("未找到确认分解按钮，确认弹窗可能未出现")
            return False
        log.info("已确认快速选择分解")

        # 等待分解完成，关闭蒙层
        time.sleep(0.2)
        self._dismiss_result_overlay()
        log.info("已关闭快速选择分解结果蒙层")
        return True

    # ========== 规则评估分解入口 ==========

    def enter_decompose_page(self) -> bool:
        """确保当前在分解页面。如果不在则尝试点击分解按钮进入。

        Returns:
            True 成功进入分解页面，False 失败
        """
        log.info("进入分解页面...")

        WindowHelper.focus()

        # 注入窗口原点，此后 MouseController 所有坐标均为窗口相对坐标
        MouseController.set_origin(WindowHelper.get_origin())

        window = WindowHelper.find_genshin_window()
        result = self._capture.capture(window=window)

        if self._is_on_decompose_page(result.image):
            log.info("已在分解页面")
            return True

        log.info("未在分解页面，尝试查找分解按钮")
        if not self._click_backpack_decompose_button(result.image):
            log.error("未找到分解按钮")
            return False

        time.sleep(1.5)
        result2 = self._capture.capture(window=window)

        if not self._is_on_decompose_page(result2.image):
            log.error("点击分解按钮后未能进入分解页面")
            return False

        log.info("已进入分解页面")
        return True

    def select_artifacts(
        self, rules: list, default_action: str, max_per_batch: int = 1000
    ) -> tuple[int, int, bool]:
        """选择一批待分解圣遗物。

        Args:
            rules: 启用的规则列表
            default_action: 默认行为
            max_per_batch: 每批最多选择数量，默认 1000，上限 1000

        Returns:
            (keep_count, discard_count, reached_limit)
        """
        return self._decompose_loop(rules, default_action, max_per_batch)

    def execute_decompose(self) -> bool:
        """点击游戏内的分解按钮并确认弹窗，完成分解。

        Returns:
            True 分解成功，False 未找到按钮或确认失败
        """
        time.sleep(0.5)
        window = WindowHelper.find_genshin_window()
        result = self._capture.capture(window=window)

        if not self._click_decompose_button(result.image):
            log.error("未找到分解按钮")
            return False
        log.info("已点击分解按钮")

        # 等待确认弹窗出现（0.2~0.4秒）
        time.sleep(0.3)
        result2 = self._capture.capture(window=window)

        confirm_pos = self._click_confirm_decompose_button(result2.image)
        if confirm_pos is None:
            log.error("未找到确认分解按钮，确认弹窗可能未出现")
            return False
        log.info("已确认分解")

        # 等待分解完成弹窗，再次点击关闭蒙层
        time.sleep(0.2)
        self._dismiss_result_overlay()
        log.info("已关闭分解结果蒙层")
        return True

    # ========== 逐格评估循环 ==========

    def _decompose_loop(
        self, rules: list, default_action: str, max_per_batch: int = 1000
    ) -> tuple[int, int, bool]:
        """逐格点击 → OCR识别 → 规则评估 → 反选保留 → 翻页。

        流程：
        1. 截图 → SlotDetector 检测格子
        2. 遍历每个格子: 点击选中 → 等待弹窗 → OCR 识别 → 规则评估
           - 命中 discard 规则 → 保持选中（待分解）
           - 命中 keep 规则 / 默认保留 → 再次点击反选
        3. PageScroller 翻页 → 回到步骤 1
        4. 无格子时停止，或选中数达到上限时停止

        Args:
            rules: 启用的规则列表
            default_action: 默认行为
            max_per_batch: 每批最多选择数量，上限 1000

        Returns:
            (keep_count, discard_count, reached_limit) 保留数、分解数、是否因达到上限而提前退出
        """
        from backend.automation.dogfood_rule_engine import DogfoodRuleEngine
        from backend.automation.page_scroller import PageScroller
        from backend.automation.slot_detector import SlotDetector
        from backend.models.slot_models import SALVAGE_SLOT_CONFIG

        config = SALVAGE_SLOT_CONFIG
        MAX_DISCARD_PER_BATCH = min(max_per_batch, 1000)
        scroller = PageScroller(MouseController(), self._capture, config)
        engine = DogfoodRuleEngine(default_action=default_action)
        iterator = SlotIterator(MouseController())

        total_keep = 0
        total_discard = 0
        reached_limit = False
        page = 0

        # 计时：用于估算剩余时间
        total_elapsed = 0.0
        timed_count = 0
        last_progress_log = 0.0  # 上次输出进度日志的时间戳

        while True:
            if self._stop_event.is_set():
                log.info("收到停止信号，退出分解循环")
                break

            page += 1
            log.info(f"--- 第 {page} 页 ---")

            # 截图并检测格子
            window = WindowHelper.find_genshin_window()
            result = self._capture.capture(window=window)

            det_result = SlotDetector.detect(result.image, config=config)
            if not det_result.slots:
                log.info("未检测到格子，分解流程结束")
                break

            log.info(
                f"第 {page} 页检测到 {len(det_result.slots)} 个格子"
                f" | 累计: 保留 {total_keep} 件, 分解 {total_discard} 件"
            )

            def on_slot(slot, idx, total, _page=page, _window=window):
                nonlocal total_keep, total_discard, reached_limit, \
                    total_elapsed, timed_count, last_progress_log

                t_start = time.perf_counter()
                log.debug(
                    f"[{_page}-{idx}/{total}] "
                    f"点击格子 ({slot.cx}, {slot.cy})"
                )

                # 截图并 OCR 识别圣遗物详情
                cap_result = self._capture.capture(window=_window)

                artifact = self._ocr_recognize_artifact(cap_result.image, config)
                if artifact is None:
                    log.warning(f"[{_page}-{idx}] OCR 识别失败")
                    return True

                # 规则评估
                action = engine.evaluate(artifact, rules)
                is_dogfood = action == "discard"

                # 计时统计
                item_time = time.perf_counter() - t_start
                total_elapsed += item_time
                timed_count += 1
                avg_time = total_elapsed / timed_count

                # 估算剩余时间
                remaining_slots_this_page = total - idx
                remaining_est = avg_time * remaining_slots_this_page

                if is_dogfood:
                    total_discard += 1
                    log.info(
                        f"[{_page}-{idx}/{total}] → 分解 "
                        f"(套装={artifact.set_name or '?'} "
                        f"部位={artifact.piece_type or '?'} "
                        f"星级={artifact.rarity or '?'}) "
                        f"| 耗时={item_time:.2f}s 平均={avg_time:.2f}s "
                        f"本页剩余≈{remaining_est:.0f}s"
                    )
                    if total_discard >= MAX_DISCARD_PER_BATCH:
                        log.info(f"已达到单批上限 {MAX_DISCARD_PER_BATCH} 件，暂停选择")
                        reached_limit = True
                        return False
                else:
                    total_keep += 1
                    log.info(
                        f"[{_page}-{idx}/{total}] → 保留 "
                        f"(套装={artifact.set_name or '?'} "
                        f"部位={artifact.piece_type or '?'} "
                        f"星级={artifact.rarity or '?'}) "
                        f"| 耗时={item_time:.2f}s 平均={avg_time:.2f}s "
                        f"本页剩余≈{remaining_est:.0f}s"
                    )
                    # 再次点击反选（取消选中）
                    MouseController.move_and_click(slot.cx, slot.cy)
                    time.sleep(0.2)

                # 每处理 10 个或每 5 秒输出一次进度日志
                now = time.perf_counter()
                if timed_count % 10 == 0 or now - last_progress_log > 5.0:
                    last_progress_log = now
                    log.info(
                        f"[进度] 已处理 {timed_count} 个 "
                        f"| 保留 {total_keep} 分解 {total_discard} "
                        f"| 平均 {avg_time:.2f}s/个"
                    )

                # 检测到锁定圣遗物，停止分解流程
                if slot.locked:
                    log.info(
                        f"[{_page}-{idx}/{total}] 检测到锁定圣遗物，"
                        f"停止分解流程 (累计保留={total_keep} 分解={total_discard})"
                    )
                    reached_limit = True
                    return False

                return True

            iterator.reset()
            iterator.iter_slots(
                det_result,
                on_slot=on_slot,
                stop_check=lambda: self._stop_event.is_set(),
            )

            if reached_limit:
                break

            if self._stop_event.is_set():
                break

            # 翻页：截图+检测 → 翻页
            window = WindowHelper.find_genshin_window()
            result = self._capture.capture(window=window)
            det_result = SlotDetector.detect(result.image, config=config)
            if not scroller.scroll_to_next_page(det_result):
                log.info("已是最后一页")
                break

        return (total_keep, total_discard, reached_limit)

    # ========== 圣遗物详情 OCR 识别 ==========

    @staticmethod
    def create_decompose_ocr_task(image: np.ndarray, config):
        """创建分解流程的圣遗物 OCR 识别任务。

        使用 SALVAGE_SLOT_CONFIG 的 detail_roi_configs 和 lock_anchor_* 参数，
        在 OcrWorker 线程中执行 ArtifactRecognizer.recognize()。

        Returns:
            callable(ocr_instance) -> ArtifactInfo | None
        """
        from backend.automation.recognizer import ArtifactRecognizer

        roi_configs = dict(config.detail_roi_configs)
        lock_search = config.lock_anchor_search_region
        lock_to_level = config.lock_anchor_to_level
        lock_to_sub = config.lock_anchor_to_sub_stats

        def task(ocr):
            try:
                artifact = ArtifactRecognizer.recognize(
                    image,
                    roi_configs,
                    ocr,
                    lock_anchor_search_region=lock_search,
                    lock_anchor_to_level=lock_to_level,
                    lock_anchor_to_sub_stats=lock_to_sub,
                )
                return artifact
            except Exception as e:
                log.debug(f"[分解OCR] 识别异常: {e}")
                return None

        return task

    @staticmethod
    def _ensure_ocr_worker_ready() -> None:
        """确保 OCR Worker 线程正在运行且模型已就绪。

        Raises:
            OcrModelNotReadyError: 模型未下载（自动完成弹窗 + 日志）
        """
        from backend.automation.ocr_model_manager import OcrModelManager
        from backend.automation.ocr_worker import OcrWorker
        from backend.exceptions.automation import OcrModelNotReadyError

        worker = OcrWorker.instance()
        if worker.isRunning():
            return

        manager = OcrModelManager()
        if not manager.is_ready():
            raise OcrModelNotReadyError()

        log.warning("OCR 模型已下载但 Worker 线程未运行，尝试启动...")
        try:
            worker.start()
        except RuntimeError:
            # QThread 只能启动一次，如果线程已结束则销毁单例并重建
            log.warning("OcrWorker 线程已终止，销毁并重建...")
            OcrWorker.destroy_instance()
            worker = OcrWorker.instance()
            worker.start()
            log.info("OcrWorker 线程已重建并启动")

    def _ocr_recognize_artifact(self, image: np.ndarray, config) -> object | None:
        """通过 OcrWorker 同步执行圣遗物详情 OCR 识别。

        使用 QEventLoop 等待异步结果，返回 ArtifactInfo 或 None。
        """
        from backend.exceptions.automation import OcrModelNotReadyError

        try:
            ArtifactDecomposer._ensure_ocr_worker_ready()
        except OcrModelNotReadyError:
            self._fatal_error = "OCR 模型未下载"
            self._stop_event.set()
            return None

        from backend.automation.ocr_worker import OcrWorker

        result_holder: list = []
        loop = QEventLoop()

        timeout_timer = QTimer()
        timeout_timer.setSingleShot(True)

        def on_timeout():
            if not result_holder:
                log.error("[分解OCR] 识别超时（30秒），请检查 OCR 模型是否正常")
            loop.quit()

        timeout_timer.timeout.connect(on_timeout)
        timeout_timer.start(30000)

        def on_done(result, _cb):
            result_holder.append(result)
            timeout_timer.stop()
            loop.quit()

        def on_error(err, _cb):
            log.debug(f"[分解OCR] 失败: {err}")
            timeout_timer.stop()
            loop.quit()

        worker = OcrWorker.instance()
        worker.task_done.connect(on_done)
        worker.task_error.connect(on_error)

        task = ArtifactDecomposer.create_decompose_ocr_task(image, config)
        worker.submit(task, callback_data="decompose")

        loop.exec()

        try:
            worker.task_done.disconnect(on_done)
            worker.task_error.disconnect(on_error)
        except Exception:
            log.debug("断开 OCR 信号连接时发生异常")

        return result_holder[0] if result_holder else None

    # ========== 模板检测 ==========

    def _is_on_decompose_page(self, image: np.ndarray) -> bool:
        """判断当前是否在分解页面。

        优先匹配「圣遗物分解文本」标题，若得分不足则用「圣遗物分解页面
        分解按钮」辅助判断（按钮在页面上则说明已在分解页面）。
        """
        # 主判断：页面标题
        text_template = TemplateManager.get("圣遗物分解文本")
        if text_template is not None and self._match_template(
            image, text_template, self.MATCH_THRESHOLD
        ):
            return True

        # 辅助判断：分解页面独有的分解按钮
        btn_template = TemplateManager.get("圣遗物分解页面分解按钮")
        if btn_template is not None:
            score, _, _, _ = multi_scale_match(image, btn_template)
            if score >= self.MATCH_THRESHOLD:
                log.info("圣遗物分解文本未匹配，但检测到分解页面按钮，判定为在分解页面")
                return True

        return False

    def _click_decompose_button(self, image: np.ndarray) -> bool:
        """查找并点击分解页面上的分解按钮（执行分解），保存坐标供后续复用"""
        template = TemplateManager.get("圣遗物分解页面分解按钮")
        if template is None:
            log.error("未找到模板: 圣遗物分解页面分解按钮")
            return False
        pos = self._match_and_click_return_pos(
            image, template, "圣遗物分解页面分解按钮"
        )
        if pos is None:
            return False
        self._decompose_button_pos = pos
        return True

    def _click_backpack_decompose_button(self, image: np.ndarray) -> bool:
        """查找并点击背包页面上的分解按钮（进入分解页面）"""
        template = TemplateManager.get("背包页面分解按钮")
        if template is None:
            log.error("未找到模板: 背包页面分解按钮")
            return False
        return self._match_and_click(image, template, "背包页面分解按钮")

    def _click_confirm_decompose_button(
        self, image: np.ndarray
    ) -> tuple[int, int] | None:
        """查找并点击确认分解弹窗中的确认按钮，返回屏幕绝对坐标"""
        template = TemplateManager.get("分解页面确认分解按钮")
        if template is None:
            log.error("未找到模板: 分解页面确认分解按钮")
            return None
        return self._match_and_click_return_pos(
            image, template, "分解页面确认分解按钮"
        )

    def _dismiss_result_overlay(self) -> None:
        """点击分解按钮位置，关闭分解结果蒙层。

        蒙层并非100%出现，点击分解按钮位置是安全的：
        - 有蒙层：点击关闭蒙层
        - 无蒙层：未选中任何圣遗物，点击无效
        """
        if self._decompose_button_pos is None:
            log.warning("分解按钮坐标丢失，无法关闭蒙层")
            return
        time.sleep(0.2)
        MouseController.move_and_click(*self._decompose_button_pos)
        time.sleep(0.2)

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
        from backend.exceptions.automation import OcrModelNotReadyError

        try:
            ArtifactDecomposer._ensure_ocr_worker_ready()
        except OcrModelNotReadyError:
            return None

        from backend.automation.ocr_worker import OcrWorker

        result_holder: list = []
        loop = QEventLoop()

        timeout_timer = QTimer()
        timeout_timer.setSingleShot(True)

        def on_timeout():
            if not result_holder:
                log.error("[快速选择OCR] 识别超时（30秒），请检查 OCR 模型是否正常")
            loop.quit()

        timeout_timer.timeout.connect(on_timeout)
        timeout_timer.start(30000)

        def on_done(result, _cb):
            result_holder.append(result)
            timeout_timer.stop()
            loop.quit()

        def on_error(err, _cb):
            log.error(f"[快速选择OCR] 失败: {err}")
            timeout_timer.stop()
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
            log.debug("断开快速选择OCR信号连接时发生异常")

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
        """模板匹配，返回是否匹配成功。"""
        score, _, _, _ = multi_scale_match(image, template)
        return score >= threshold

    def _match_and_click(
        self, image: np.ndarray, template: object, name: str
    ) -> bool:
        """模板匹配成功后点击，返回是否成功。"""
        return self._match_and_click_return_pos(image, template, name) is not None

    def _match_and_click_return_pos(
        self, image: np.ndarray, template: object, name: str
    ) -> tuple[int, int] | None:
        """模板匹配成功后点击中心位置，返回屏幕绝对坐标。

        与 _match_and_click 逻辑相同，但额外返回点击坐标，
        供后续复用（如快速选择按钮的二次点击）。
        """
        score, (rel_x, rel_y), scale, (_w, _h) = multi_scale_match(image, template)
        if score < self.MATCH_THRESHOLD:
            log.warning(
                f"[{name}] 匹配失败: 得分={score:.3f} < 阈值={self.MATCH_THRESHOLD}"
            )
            return None

        abs_x, abs_y = WindowHelper.to_absolute(rel_x, rel_y)
        win_origin = WindowHelper.get_origin()
        log.info(
            f"[{name}] 匹配成功: 得分={score:.3f} 缩放={scale:.2f} "
            f"窗口相对=({rel_x}, {rel_y}) 窗口原点={win_origin} "
            f"屏幕绝对=({abs_x}, {abs_y})"
        )
        MouseController.move_and_click(rel_x, rel_y)
        return (rel_x, rel_y)