"""
设置页面
========
软件所有可配置项集中在此页面，通过 settings 单例持久化到 settings.db。
"""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QShowEvent
from PyQt6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from utils.datetime_helper import DateTimeHelper
from utils.logger import log
from utils.settings_manager import settings

from backend.automation.ocr_model_manager import OcrModelManager
from backend.ui.presenters.sync_worker import SyncWorker


class SettingsPage(QWidget):
    """设置页面 — 通过构造函数回调与外部通信，无需 MainWindow 手动连接信号"""

    def __init__(
        self,
        on_theme_changed: Callable[[str], None] | None = None,
        on_status: Callable[[str, int, str], None] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._on_theme_changed = on_theme_changed or (lambda _: None)
        self._on_status = on_status or (lambda m, d=0, l="INFO": None)
        self._sync_worker: SyncWorker | None = None
        self._model_manager = OcrModelManager()
        self._download_worker = None

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title = QLabel("设置")
        title.setProperty("class", "section-title")
        layout.addWidget(title)

        # --- 外观设置 ---
        group_appearance = QGroupBox("外观设置")
        form = QFormLayout()
        form.setSpacing(12)

        self._combo_theme = QComboBox()
        self._combo_theme.addItems(["深色", "浅色"])
        self._combo_theme.setToolTip("切换应用主题")
        self._combo_theme.currentIndexChanged.connect(self._on_theme_changed_internal)
        form.addRow("主题:", self._combo_theme)

        group_appearance.setLayout(form)
        layout.addWidget(group_appearance)

        # --- 数据同步 ---
        group_sync = QGroupBox("圣遗物同步")
        sync_layout = QVBoxLayout()
        sync_layout.setSpacing(8)

        # 按钮行
        btn_row = QHBoxLayout()
        self._btn_sync = QPushButton("立即同步")
        self._btn_sync.setProperty("class", "primary")
        self._btn_sync.clicked.connect(self._on_sync)
        btn_row.addWidget(self._btn_sync)
        btn_row.addStretch()
        sync_layout.addLayout(btn_row)

        # 进度条
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)  # 不确定模式
        self._progress.setVisible(False)
        sync_layout.addWidget(self._progress)

        # 同步状态
        self._label_sync_time = QLabel()
        self._label_sync_time.setProperty("class", "hint")
        sync_layout.addWidget(self._label_sync_time)

        self._label_sync_stats = QLabel()
        self._label_sync_stats.setProperty("class", "hint")
        sync_layout.addWidget(self._label_sync_stats)

        group_sync.setLayout(sync_layout)
        layout.addWidget(group_sync)

        # --- OCR 模型 ---
        group_model = QGroupBox("OCR 模型")
        model_layout = QVBoxLayout()
        model_layout.setSpacing(8)

        btn_row2 = QHBoxLayout()
        self._btn_download_models = QPushButton("下载模型")
        self._btn_download_models.setProperty("class", "primary")
        self._btn_download_models.clicked.connect(self._on_download_models)
        btn_row2.addWidget(self._btn_download_models)
        btn_row2.addStretch()
        model_layout.addLayout(btn_row2)

        self._model_progress = QProgressBar()
        self._model_progress.setRange(0, 0)
        self._model_progress.setVisible(False)
        model_layout.addWidget(self._model_progress)

        self._label_model_status = QLabel()
        self._label_model_status.setProperty("class", "hint")
        model_layout.addWidget(self._label_model_status)

        self._label_model_version = QLabel()
        self._label_model_version.setProperty("class", "hint")
        model_layout.addWidget(self._label_model_version)

        group_model.setLayout(model_layout)
        layout.addWidget(group_model)

        layout.addStretch()

        self._load_settings()

    # ---------- 加载 / 保存 ----------

    def _load_settings(self) -> None:
        """从 settings 单例加载当前值"""
        theme = settings.get_theme()
        self._combo_theme.setCurrentIndex(0 if theme == "dark" else 1)
        self._refresh_sync_status()
        self._refresh_model_status()

    def showEvent(self, event: QShowEvent) -> None:
        """页面显示时刷新同步时间，保证"上次同步"始终准确"""
        self._refresh_sync_status()
        self._refresh_model_status()
        super().showEvent(event)

    def _on_theme_changed_internal(self) -> None:
        """主题切换 → 持久化 → 通知外部"""
        theme = "dark" if self._combo_theme.currentIndex() == 0 else "light"
        settings.set_theme(theme)
        self._on_theme_changed(theme)

    # ---------- 数据同步 ----------

    def _refresh_sync_status(self) -> None:
        """刷新同步时间和统计信息"""
        ts = settings.get_int("data.last_sync_ts")
        self._label_sync_time.setText(
            f"上次同步: {DateTimeHelper.relative_time(ts if ts > 0 else None)}"
        )
        sets = settings.get_int("data.last_sync_sets")
        slots = settings.get_int("data.last_sync_pieces")
        expected = settings.get_int("data.last_sync_expected")
        if sets > 0:
            if expected > 0:
                rate = slots / expected * 100
                self._label_sync_stats.setText(
                    f"已同步 {sets} 个套装，{slots} 个部位，"
                    f"期望{expected}个，达成率{rate:.1f}%"
                )
            else:
                self._label_sync_stats.setText(
                    f"已同步 {sets} 个套装，{slots} 个部位"
                )
        else:
            self._label_sync_stats.setText("尚未同步数据")

    def _on_sync(self) -> None:
        """开始同步"""
        self._btn_sync.setEnabled(False)
        self._progress.setVisible(True)
        self._label_sync_time.setText("正在同步…")
        self._on_status("正在同步圣遗物数据…", 0, "INFO")

        self._sync_worker = SyncWorker()
        self._sync_worker.progress.connect(self._on_progress)
        self._sync_worker.finished_sync.connect(self._on_sync_finished)
        self._sync_worker.failed.connect(self._on_sync_failed)
        self._sync_worker.start()

    def _on_progress(self, current: int, total: int, name: str) -> None:
        """更新进度条"""
        if self._progress.maximum() != total:
            self._progress.setRange(0, total)
        self._progress.setValue(current)
        self._label_sync_time.setText(f"正在同步… {current}/{total}")
        self._on_status(f"正在同步: {current}/{total}  {name}", 0, "INFO")

    def _on_sync_finished(self, sets_count: int, slots_count: int, expected_count: int) -> None:
        """同步完成"""
        import time

        now_ts = time.time()
        settings.set("data.last_sync_ts", str(int(now_ts)))
        settings.set("data.last_sync_sets", str(sets_count))
        settings.set("data.last_sync_pieces", str(slots_count))
        settings.set("data.last_sync_expected", str(expected_count))

        self._btn_sync.setEnabled(True)
        self._progress.setVisible(False)
        self._refresh_sync_status()
        self._on_status("同步完成", 3000, "SUCCESS")

    def _on_sync_failed(self, error: str) -> None:
        """同步失败"""
        self._btn_sync.setEnabled(True)
        self._progress.setVisible(False)
        self._label_sync_time.setText(f"同步失败: {error}")
        self._on_status(f"同步失败: {error}", 5000, "ERROR")

    # ---------- OCR 模型下载 ----------

    def _refresh_model_status(self) -> None:
        """刷新模型状态显示"""
        if self._model_manager.is_ready():
            self._label_model_status.setText("[√]模型就绪")
            self._btn_download_models.setEnabled(True)
            self._btn_download_models.setText("重新下载")
        else:
            missing = self._model_manager.get_missing_models()
            self._label_model_status.setText(f"[!] 缺少模型: {', '.join(missing)}")
            self._btn_download_models.setEnabled(True)
            self._btn_download_models.setText("下载模型")
        self._label_model_version.setText(self._model_manager.get_version_summary())

    def _on_download_models(self) -> None:
        """开始下载模型"""
        self._btn_download_models.setEnabled(False)
        self._btn_download_models.setText("下载中…")
        self._model_progress.setVisible(True)
        self._model_progress.setRange(0, 0)
        self._label_model_status.setText("正在清空旧模型…")

        self._download_worker = self._model_manager.create_download_worker()
        self._download_worker.progress.connect(self._on_download_progress)
        self._download_worker.finished_download.connect(self._on_download_finished)
        self._download_worker.start()

    def _on_download_progress(self, current: int, total: int, status: str) -> None:
        if self._model_progress.maximum() != total:
            self._model_progress.setRange(0, total)
        self._model_progress.setValue(current)
        self._label_model_status.setText(f"正在下载… {current}/{total}")
        log.info(status)

    def _on_download_finished(self, success: bool, message: str) -> None:
        self._model_progress.setVisible(False)
        self._refresh_model_status()
        if success:
            log.info(message)
        else:
            log.error(message)