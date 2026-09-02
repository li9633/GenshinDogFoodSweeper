from __future__ import annotations

"""自动锁定/解锁圣遗物模块

流程与分解流程基本一致：
1. 截图 → SlotDetector 检测格子
2. 遍历每个格子: 点击打开详情 → OCR 识别 → 规则评估
   - 命中 keep 规则 → 锁定
   - 命中 discard 规则 → 解锁
3. PageScroller 翻页 → 回到步骤 1
4. 无格子时停止
"""

import threading
import time

import numpy as np
from PySide6.QtCore import QEventLoop, QObject, QTimer
from utils.logger import log

from backend.automation.mouse_controller import MouseController
from backend.automation.template_manager import TemplateManager
from backend.automation.template_matcher import multi_scale_match
from backend.automation.window_helper import WindowHelper
from backend.exceptions.automation.exceptions import LockIconNotFoundError
from backend.utils.screen_capture import ScreenshotCapture


class ArtifactLocker(QObject):
    """自动锁定/解锁圣遗物"""

    def __init__(self) -> None:
        super().__init__()
        self._capture = ScreenshotCapture()
        self._stop_event = threading.Event()
        self._fatal_error: str | None = None
        self._lock_icon_center: tuple[int, int] | None = None

    def stop(self) -> None:
        self._stop_event.set()
        log.debug("停止标志已设置")

    def reset_stop(self) -> None:
        self._stop_event.clear()
        self._fatal_error = None
        self._lock_icon_center = None

    # ========== 入口 ==========

    def lock_artifacts(
        self, rules: list, default_action: str, re_unlock: bool = False,
        max_count: int = 0,
    ) -> tuple[int, int, int]:
        """执行锁定/解锁流程。

        Args:
            rules: 启用的规则列表
            default_action: 默认行为 ("keep" 或 "discard")
            re_unlock: 是否将已锁定的圣遗物重新解锁
            max_count: 最大处理数量，0 表示处理到停止

        Returns:
            (locked_count, unlocked_count, skipped_count)
        """
        return self._lock_loop(rules, default_action, re_unlock, max_count)

    # ========== 主循环 ==========

    def _lock_loop(
        self, rules: list, default_action: str, re_unlock: bool, max_count: int,
    ) -> tuple[int, int, int]:
        """逐格点击 → OCR识别 → 规则评估 → 锁定/解锁 → 翻页。"""
        from backend.automation.dogfood_rule_engine import DogfoodRuleEngine
        from backend.automation.page_scroller import PageScroller
        from backend.automation.slot_detector import SlotDetector
        from backend.models.slot_models import BAG_SLOT_CONFIG

        config = BAG_SLOT_CONFIG
        scroller = PageScroller(MouseController(), self._capture, config)
        engine = DogfoodRuleEngine(default_action=default_action)

        total_locked = 0
        total_unlocked = 0
        total_skipped = 0
        page = 0

        WindowHelper.focus()
        MouseController.set_origin(WindowHelper.get_origin())

        while True:
            if self._stop_event.is_set():
                log.info("收到停止信号，退出锁定循环")
                break

            page += 1
            log.info(f"--- 第 {page} 页 ---")

            window = WindowHelper.find_genshin_window()
            result = self._capture.capture(window=window)
            if result is None:
                log.warning("截图失败")
                break

            det_result = SlotDetector.detect(result.image, config=config)
            if not det_result.slots:
                log.info("未检测到格子，锁定流程结束")
                break

            log.info(
                f"第 {page} 页检测到 {len(det_result.slots)} 个格子"
                f" | 累计: 锁定 {total_locked} 件, 解锁 {total_unlocked} 件, "
                f"跳过 {total_skipped} 件"
            )

            for idx, slot in enumerate(det_result.slots):
                if self._stop_event.is_set():
                    break

                # 达到处理上限时停止
                total_processed = total_locked + total_unlocked + total_skipped
                if max_count > 0 and total_processed >= max_count:
                    log.info(f"已达到处理上限 {max_count} 件，停止")
                    break

                t_start = time.perf_counter()
                log.debug(
                    f"[{page}-{idx + 1}/{len(det_result.slots)}] "
                    f"点击格子 ({slot.cx}, {slot.cy})"
                )

                # 点击打开详情弹窗
                MouseController.move_and_click(slot.cx, slot.cy)
                time.sleep(0.35)

                # OCR 识别圣遗物详情
                cap_result = self._capture.capture(window=window)
                if cap_result is None:
                    continue

                artifact = self._ocr_recognize_artifact(cap_result.image, config)
                if artifact is None:
                    log.warning(f"[{page}-{idx + 1}] OCR 识别失败")
                    continue

                # 跳过强化材料
                if artifact.is_material:
                    total_skipped += 1
                    log.debug(
                        f"[{page}-{idx + 1}] 跳过强化材料: {artifact.material_name}"
                    )
                    continue

                # 规则评估：返回 "keep" 或 "discard"
                action = engine.evaluate(artifact, rules)
                should_lock = action == "keep"
                is_locked = artifact.is_locked

                t_eval = time.perf_counter()
                item_time = t_eval - t_start

                artifact_desc = (
                    f"套装={artifact.set_name or '?'} "
                    f"部位={artifact.piece_type or '?'} "
                    f"星级={artifact.rarity or '?'}"
                )

                # 缓存锁定图标坐标（窗口位置不变，首次匹配后复用）
                if self._lock_icon_center is None:
                    self._lock_icon_center = self._find_lock_icon_center(
                        cap_result.image
                    )
                    if self._lock_icon_center is None:
                        raise LockIconNotFoundError()

                if is_locked:
                    if should_lock:
                        total_skipped += 1
                        log.info(
                            f"[{page}-{idx + 1}] → 跳过(已锁定) {artifact_desc} "
                            f"| 耗时={item_time:.2f}s"
                        )
                    elif re_unlock:
                        self._click_lock_icon()
                        total_unlocked += 1
                        log.info(
                            f"[{page}-{idx + 1}] → 解锁 {artifact_desc} "
                            f"| 耗时={item_time:.2f}s"
                        )
                    else:
                        total_skipped += 1
                        log.info(
                            f"[{page}-{idx + 1}] → 跳过(已锁定且不重新解锁) "
                            f"{artifact_desc} | 耗时={item_time:.2f}s"
                        )
                else:
                    if should_lock:
                        self._click_lock_icon()
                        total_locked += 1
                        log.info(
                            f"[{page}-{idx + 1}] → 锁定 {artifact_desc} "
                            f"| 耗时={item_time:.2f}s"
                        )
                    else:
                        total_skipped += 1
                        log.info(
                            f"[{page}-{idx + 1}] → 跳过(已解锁) {artifact_desc} "
                            f"| 耗时={item_time:.2f}s"
                        )

            if self._stop_event.is_set():
                break

            # 翻页（坐标均为窗口相对坐标，MouseController 自动转换）
            flag_x = config.roi[0] + config.roi[2] // 2
            flag_y = config.roi[1] + config.roi[3] // 2
            if not scroller.scroll_to_next_page(flag_x, flag_y):
                log.info("已是最后一页")
                break

        return (total_locked, total_unlocked, total_skipped)

    # ========== 锁定图标点击 ==========

    def _click_lock_icon(self) -> None:
        """点击锁定图标（使用缓存坐标）。"""
        cx, cy = self._lock_icon_center  # type: ignore[misc]
        MouseController.move_and_click(cx, cy)
        time.sleep(0.25)

    @staticmethod
    def _find_lock_icon_center(
        image: np.ndarray,
    ) -> tuple[int, int] | None:
        """通过模板匹配找到锁定图标中心坐标。

        优先匹配「解锁」状态（大部分圣遗物都是解锁的），
        失败后再匹配「锁定」状态。

        Returns:
            (cx, cy) 锁定图标中心坐标（图像坐标），未找到返回 None
        """
        for key in ("圣遗物状态已解锁", "圣遗物状态已锁定"):
            template = TemplateManager.get(key)
            if template is None:
                continue
            region = template.region
            if region is None:
                continue
            rx, ry, rw, rh = region
            if (
                rx < 0 or ry < 0
                or rx + rw > image.shape[1]
                or ry + rh > image.shape[0]
            ):
                continue
            score, (cx, cy), _scale, (_tw, _th) = multi_scale_match(
                image, template, search_region=region
            )
            if score >= 0.8:
                return (cx, cy)
        return None

    # ========== OCR 识别 ==========

    @staticmethod
    def _create_ocr_task(image: np.ndarray, config):
        """创建圣遗物 OCR 识别任务。"""
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
                log.debug(f"[锁定OCR] 识别异常: {e}")
                return None

        return task

    @staticmethod
    def _ensure_ocr_worker_ready() -> None:
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
            log.warning("OcrWorker 线程已终止，销毁并重建...")
            OcrWorker.destroy_instance()
            worker = OcrWorker.instance()
            worker.start()
            log.info("OcrWorker 线程已重建并启动")

    def _ocr_recognize_artifact(self, image: np.ndarray, config) -> object | None:
        from backend.exceptions.automation import OcrModelNotReadyError

        try:
            ArtifactLocker._ensure_ocr_worker_ready()
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
                log.error("[锁定OCR] 识别超时（30秒），请检查 OCR 模型是否正常")
            loop.quit()

        timeout_timer.timeout.connect(on_timeout)
        timeout_timer.start(30000)

        def on_done(result, _cb):
            result_holder.append(result)
            timeout_timer.stop()
            loop.quit()

        def on_error(err, _cb):
            log.debug(f"[锁定OCR] 失败: {err}")
            timeout_timer.stop()
            loop.quit()

        worker = OcrWorker.instance()
        worker.task_done.connect(on_done)
        worker.task_error.connect(on_error)

        task = ArtifactLocker._create_ocr_task(image, config)
        worker.submit(task, callback_data="locker")

        loop.exec()

        try:
            worker.task_done.disconnect(on_done)
            worker.task_error.disconnect(on_error)
        except Exception:
            log.debug("断开 OCR 信号连接时发生异常")

        return result_holder[0] if result_holder else None