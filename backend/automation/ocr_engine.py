"""OCR 引擎 — PaddleOCR 懒加载封装"""

from __future__ import annotations

from pathlib import Path

from utils.logger import log

from backend.automation.ocr_model_manager import OcrModelManager


class OcrEngine:
    """PaddleOCR 引擎封装，支持懒加载和模型就绪检查"""

    _ocr: object | None = None  # 类变量，所有实例共享同一模型

    def __init__(self, engines_dir: Path | None = None):
        if engines_dir is None:
            engines_dir = Path(__file__).resolve().parents[2] / "engines"
        self._engines_dir = engines_dir
        self._model_manager = OcrModelManager(engines_dir)

    # ---------- PaddleOCR 实例创建（唯一入口） ----------

    @staticmethod
    def _create_paddle_ocr(engines_dir: Path):
        """创建 PaddleOCR 实例。

        设置所需环境变量并初始化模型。此方法可在任意线程中调用，
        OcrEngine 和 OcrWorker 均通过此方法创建各自的 OCR 实例。
        """
        import os

        os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
        os.environ.setdefault("FLAGS_use_onednn", "False")
        os.environ.setdefault("FLAGS_use_mkldnn", "0")
        os.environ.setdefault("FLAGS_enable_pir_api", "False")
        os.environ.setdefault("PADDLEX_HOME", str(engines_dir))

        from paddleocr import PaddleOCR

        models_dir = engines_dir / "official_models"
        return PaddleOCR(
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            text_detection_model_name="PP-OCRv5_mobile_det",
            text_detection_model_dir=str(models_dir / "PP-OCRv5_mobile_det"),
            text_recognition_model_name="PP-OCRv5_mobile_rec",
            text_recognition_model_dir=str(models_dir / "PP-OCRv5_mobile_rec"),
        )

    # ---------- 公开 API ----------

    @property
    def is_ready(self) -> bool:
        return self._model_manager.is_ready()

    def warm_up(self) -> None:
        """预热 OCR 引擎，在后台线程中调用以避免阻塞 UI"""
        self.get()

    def get(self):
        """获取 OCR 实例，首次调用时自动加载模型"""
        if OcrEngine._ocr is None:
            if not self._model_manager.is_ready():
                raise RuntimeError("OCR 模型未下载，请前往「设置」页面点击「下载模型」")

            log.info("首次加载 OCR 引擎（3-5 秒）…")
            OcrEngine._ocr = OcrEngine._create_paddle_ocr(self._engines_dir)
            log.info("OCR 引擎就绪")
        return OcrEngine._ocr