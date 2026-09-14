"""OCR 初始化器
==============
窗口就绪时检查 OCR 模型是否已下载：

- 未下载 → 抛 :class:`OcrModelNotReadyError`（只带消息；由 UI 层决定如何提示）
- 已下载 → 启动 OcrWorker 后台线程（异步加载模型，不阻塞 UI）

本模块属于自动化层，**不依赖 UI**：窗口就绪的注册由入口（``backend/main.py``）
通过 ``OnWindowReady`` 完成。

模型检查是轻量操作（文件存在性检查），不涉及模型加载；
实际模型加载仍在 OcrWorker 后台线程中完成。
"""

from __future__ import annotations

from backend.utils.logger import log


class OcrInitializer:
    """OCR 初始化器：窗口就绪时检查模型 → 启动 Worker"""

    def on_window_ready(self) -> None:
        from backend.automation.ocr_model_manager import OcrModelManager
        from backend.exceptions.automation import OcrModelNotReadyError

        manager = OcrModelManager()
        if not manager.is_ready():
            raise OcrModelNotReadyError()

        from backend.automation.ocr_worker import OcrWorker

        worker = OcrWorker.instance()
        worker.start()
        log.info("OCR Worker 线程已启动，模型将在后台异步加载")
