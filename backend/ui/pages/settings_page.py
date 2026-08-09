"""
设置页面
========
软件所有可配置项集中在此页面，通过 settings 单例持久化到 settings.db。
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QThread, pyqtSignal
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
from utils.settings_manager import settings


class _SyncWorker(QThread):
    """后台线程：执行圣遗物数据同步"""

    finished_sync = pyqtSignal(int, int, int)  # (sets_count, slots_count, expected_count)
    progress = pyqtSignal(int, int, str)  # (current, total, set_name)
    failed = pyqtSignal(str)

    def run(self) -> None:
        from crawler.artifact_set_fetcher import ArtifactSetFetcher

        try:
            data = ArtifactSetFetcher.run_concurrent(
                progress_callback=self.progress.emit
            )
            total_slots = sum(len(item.get("slots", [])) for item in data)
            total_expected = 0
            for item in data:
                effects = item.get("setEffects", {})
                if "1pc" in effects and "2pc" not in effects and "4pc" not in effects:
                    total_expected += 1
                else:
                    total_expected += 5
            self.finished_sync.emit(len(data), total_slots, total_expected)
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e))


class SettingsPage(QWidget):
    """设置页面 — 主题变更通过 theme_changed 信号通知 MainWindow"""

    theme_changed = pyqtSignal(str)
    sync_started = pyqtSignal()
    sync_finished = pyqtSignal()
    sync_progress = pyqtSignal(int, int, str)  # 转发给 MainWindow → 状态栏

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sync_worker: _SyncWorker | None = None

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
        self._combo_theme.currentIndexChanged.connect(self._on_theme_changed)
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

        layout.addStretch()

        self._load_settings()

    # ---------- 加载 / 保存 ----------

    def _load_settings(self) -> None:
        """从 settings 单例加载当前值"""
        theme = settings.get_theme()
        self._combo_theme.setCurrentIndex(0 if theme == "dark" else 1)
        self._refresh_sync_status()

    def showEvent(self, event: QShowEvent) -> None:
        """页面显示时刷新同步时间，保证"上次同步"始终准确"""
        self._refresh_sync_status()
        super().showEvent(event)

    def _on_theme_changed(self) -> None:
        """主题切换 → 持久化 → 通知 MainWindow 刷新样式"""
        theme = "dark" if self._combo_theme.currentIndex() == 0 else "light"
        settings.set_theme(theme)
        self.theme_changed.emit(theme)

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
        self.sync_started.emit()

        self._sync_worker = _SyncWorker()
        self._sync_worker.progress.connect(self._on_progress)
        self._sync_worker.progress.connect(self.sync_progress.emit)
        self._sync_worker.finished_sync.connect(self._on_sync_finished)
        self._sync_worker.failed.connect(self._on_sync_failed)
        self._sync_worker.start()

    def _on_progress(self, current: int, total: int, name: str) -> None:
        """更新进度条"""
        if self._progress.maximum() != total:
            self._progress.setRange(0, total)
        self._progress.setValue(current)
        self._label_sync_time.setText(f"正在同步… {current}/{total}")

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
        self.sync_finished.emit()

    def _on_sync_failed(self, error: str) -> None:
        """同步失败"""
        self._btn_sync.setEnabled(True)
        self._progress.setVisible(False)
        self._label_sync_time.setText(f"同步失败: {error}")
        self.sync_finished.emit()