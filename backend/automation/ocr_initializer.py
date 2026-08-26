"""OCR 初始化器 — OnWindowReady 实现
===================================
窗口就绪时检查 OCR 模型是否已下载：
- 未下载 → log.error + GMessageBox 弹窗提示用户
- 已下载 → 启动 OcrWorker 后台线程（异步加载模型，不阻塞 UI）

模型检查是轻量操作（文件存在性检查），不涉及模型加载。
实际模型加载仍在 OcrWorker 后台线程中完成。
"""

from __future__ import annotations

from PySide6.QtCore import QObject
from ui.lifecycle import OnWindowReady
from utils.logger import log


class OcrInitializer(QObject, OnWindowReady):
    """OCR 初始化器：窗口就绪时检查模型 → GMessageBox 弹窗 / 启动 Worker"""

    def __init__(self, parent: QObject | None = None):
        QObject.__init__(self, parent)
        OnWindowReady.__init__(self)

    def on_window_ready(self) -> None:
        from backend.automation.ocr_model_manager import OcrModelManager
        from backend.exceptions.automation import OcrModelNotReadyError

        manager = OcrModelManager()
        if not manager.is_ready():
            raise OcrModelNotReadyError()  # 自动完成 log.error + GMessageBox 弹窗

        from backend.automation.ocr_worker import OcrWorker

        worker = OcrWorker.instance()
        worker.start()
        log.info("OCR Worker 线程已启动，模型将在后台异步加载")