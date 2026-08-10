"""OCR 模型下载管理器 — 管理 PaddleOCR 模型的本地下载、版本追踪"""

from __future__ import annotations

import json
import logging
import shutil
import tempfile
import time
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal
from utils.logger import log

# 抑制 modelscope 下载时的 INFO 日志（进度条噪音）
logging.getLogger("modelscope_hub.download").setLevel(logging.WARNING)

# ---- 模型定义 ----
_MODELS: list[dict] = [
    {
        "name": "PP-OCRv5_mobile_det",
        "modelscope_id": "PaddlePaddle/PP-OCRv5_mobile_det",
        "check_file": "inference.pdiparams",
    },
    {
        "name": "PP-OCRv5_mobile_rec",
        "modelscope_id": "PaddlePaddle/PP-OCRv5_mobile_rec",
        "check_file": "inference.pdiparams",
    },
]

_MODELSCOPE_REVISION = "master"


class _DownloadWorker(QThread):
    """后台线程：下载 OCR 模型"""

    progress = pyqtSignal(int, int, str)  # (current, total, status_text)
    finished_download = pyqtSignal(bool, str)  # (success, message)

    def __init__(self, engines_dir: Path, parent=None):
        super().__init__(parent)
        self._engines_dir = engines_dir

    def run(self) -> None:
        from modelscope.hub.snapshot_download import snapshot_download
        from modelscope_hub._download import ProgressCallback

        models_dir = self._engines_dir / "official_models"

        # 清空旧模型，确保每次都是全新下载
        if models_dir.exists():
            shutil.rmtree(models_dir)
        models_dir.mkdir(parents=True, exist_ok=True)

        total = len(_MODELS)
        downloaded: list[str] = []
        failed: list[str] = []

        for i, model in enumerate(_MODELS):
            name = model["name"]
            target_dir = models_dir / name

            if (target_dir / model["check_file"]).exists():
                self.progress.emit(i + 1, total, f"{name} 已存在，跳过")
                downloaded.append(name)
                continue

            self.progress.emit(i, total, f"正在下载 {name}…")

            worker_ref = self
            current_model_idx = i
            current_model_name = name

            class _SignalCallback(ProgressCallback):
                def __init__(self, filename, file_size, _w=worker_ref):
                    super().__init__(filename, file_size)
                    self._worker = _w

                def update(self, size: int, _idx=current_model_idx, _name=current_model_name) -> None:
                    pct = size / self.file_size * 100 if self.file_size > 0 else 0
                    self._worker.progress.emit(
                        _idx,
                        total,
                        f"{_name} — {self.filename} ({size}/{self.file_size}, {pct:.1f}%)",
                    )

            try:
                with tempfile.TemporaryDirectory() as tmp_dir:
                    snapshot_download(
                        model["modelscope_id"],
                        revision=_MODELSCOPE_REVISION,
                        local_dir=tmp_dir,
                        progress_callbacks=[_SignalCallback],
                    )
                    # snapshot_download 保留 repo 相对路径结构，
                    # 递归查找 model pd 文件所在目录，复制到目标位置
                    tmp_path = Path(tmp_dir)
                    found = list(tmp_path.rglob(model["check_file"]))
                    if found:
                        src_dir = found[0].parent
                        shutil.copytree(src_dir, target_dir, dirs_exist_ok=True)
                    else:
                        # 兜底：直接复制整个下载目录
                        shutil.copytree(tmp_path, target_dir, dirs_exist_ok=True)

                downloaded.append(name)
                self.progress.emit(i + 1, total, f"{name} 下载完成")
                log.info(f"OCR 模型 {name} 下载完成 → {target_dir}")
            except Exception as e:  # noqa: BLE001
                failed.append(name)
                log.error(f"OCR 模型 {name} 下载失败: {e}")

        if downloaded:
            version_file = self._engines_dir / "version.json"
            version_file.write_text(
                json.dumps(
                    {
                        "models": {m: _MODELSCOPE_REVISION for m in downloaded},
                        "downloaded_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "downloaded_ts": int(time.time()),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

        if failed:
            self.finished_download.emit(
                False,
                f"部分模型下载失败: {', '.join(failed)}，"
                f"已下载: {', '.join(downloaded) if downloaded else '无'}",
            )
        else:
            self.finished_download.emit(True, f"全部 {len(downloaded)} 个模型就绪")


class OcrModelManager:
    """OCR 模型管理器 — 下载、状态检查、版本追踪"""

    def __init__(self, engines_dir: Path | None = None):
        if engines_dir is None:
            engines_dir = Path(__file__).resolve().parents[2] / "engines"
        self._engines_dir = Path(engines_dir)
        self._models_dir = self._engines_dir / "official_models"

    @property
    def engines_dir(self) -> Path:
        return self._engines_dir

    @property
    def models_dir(self) -> Path:
        return self._models_dir

    def is_ready(self) -> bool:
        """检查所有模型是否已就绪"""
        return len(self.get_missing_models()) == 0

    def get_missing_models(self) -> list[str]:
        """返回尚未就绪的模型名称列表"""
        missing: list[str] = []
        for model in _MODELS:
            check_file = self._models_dir / model["name"] / model["check_file"]
            if not check_file.exists():
                missing.append(model["name"])
        return missing

    def get_version_info(self) -> dict:
        """获取本地版本信息"""
        version_file = self._engines_dir / "version.json"
        if version_file.exists():
            try:
                return json.loads(version_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        return {}

    def get_version_summary(self) -> str:
        """返回版本信息的可读摘要"""
        info = self.get_version_info()
        if not info:
            return "未下载"
        ts = info.get("downloaded_ts", 0)
        if ts:
            dt = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))
            models = info.get("models", {})
            return f"已下载 {len(models)} 个模型 ({dt})"
        return "版本信息异常"

    def create_download_worker(self) -> _DownloadWorker:
        """创建下载工作线程"""
        return _DownloadWorker(self._engines_dir)