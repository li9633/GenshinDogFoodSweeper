"""OCR Worker — 在专用线程中执行 PaddleOCR 推理，解决线程安全问题并避免阻塞 UI

PaddleOCR 要求初始化和推理必须在同一线程中执行。
本模块提供 OcrWorker（QThread 子类），在 run() 中初始化模型，
通过队列接收任务，所有推理都在 Worker 线程中完成，结果通过信号返回主线程。

使用方式（单例）:
    worker = OcrWorker.instance()
    worker.start()
    worker.submit(lambda ocr: ocr.ocr(image), callback_data="id1")
"""

from __future__ import annotations

import queue
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import Any, ClassVar

from PySide6.QtCore import QThread, Signal
from utils.logger import log


class OcrWorker(QThread):
    """在专用线程中运行 PaddleOCR。

    单例模式：整个应用共享一个 Worker 实例。
    模型初始化和所有推理都在同一个线程中执行，
    避免 PaddleOCR 的跨线程安全问题，同时不阻塞 UI 线程。
    """

    _instance: ClassVar[OcrWorker | None] = None

    ready = Signal()  # OCR 模型就绪
    task_done = Signal(object, object)  # (result, callback_data)
    task_error = Signal(str, object)  # (error_message, callback_data)

    def __init__(self, engines_dir: Path | None = None):
        super().__init__()
        if engines_dir is None:
            engines_dir = Path(__file__).resolve().parents[2] / "engines"
        self._engines_dir = engines_dir
        self._queue: queue.Queue = queue.Queue()
        self._ocr: Any = None

    @classmethod
    def instance(cls, engines_dir: Path | None = None) -> OcrWorker:
        """获取全局单例（仅创建实例，不启动线程）

        线程启动由 OcrInitializer.on_window_ready() 统一控制，
        确保模型检查通过后才启动。
        """
        if cls._instance is None:
            cls._instance = OcrWorker(engines_dir)
        return cls._instance

    @classmethod
    def destroy_instance(cls) -> None:
        """销毁单例并停止线程"""
        if cls._instance is not None:
            cls._instance.stop()
            cls._instance = None

    def run(self) -> None:
        """线程主循环：初始化 PaddleOCR → 处理任务队列

        模型就绪检查已在 OcrInitializer.on_window_ready() 中完成，
        此处直接创建 OCR 实例。
        """
        try:
            from utils.log_bridge import TaskContext

            from backend.automation.ocr_engine import OcrEngine
            from backend.exceptions.automation import OcrModelNotReadyError

            with TaskContext("ocr_init", "OCR 引擎预热中 …", success_message="OCR 引擎就绪"):
                self._ocr = OcrEngine.create_ocr(self._engines_dir)
            self.ready.emit()

            # ---- 任务处理循环 ----
            while True:
                try:
                    task = self._queue.get(timeout=0.5)
                except queue.Empty:
                    continue

                if task is None:  # 停止信号
                    break

                fn, callback_data = task
                try:
                    result = fn(self._ocr)
                    self.task_done.emit(result, callback_data)
                except Exception:
                    tb = traceback.format_exc()
                    log.error(f"OCR 识别失败:\n{tb}")
                    self.task_error.emit(tb, callback_data)

        except OcrModelNotReadyError:
            self.task_error.emit(
                "OCR 模型未下载，请前往「设置」页面点击「下载模型」", None
            )
        except Exception:
            tb = traceback.format_exc()
            log.error(f"OCR 引擎初始化失败:\n{tb}")
            self.task_error.emit(tb, None)

    def submit(self, fn: Callable[[Any], Any], callback_data: Any = None) -> None:
        """提交任务到 OCR 工作线程（线程安全）。

        Args:
            fn: callable(ocr_instance) -> result，在 Worker 线程中执行
            callback_data: 随结果一起通过 task_done/task_error 信号返回的标识数据
        """
        self._queue.put((fn, callback_data))

    def stop(self) -> None:
        """停止工作线程（阻塞等待最多 5 秒）"""
        self._queue.put(None)
        self.wait(5000)