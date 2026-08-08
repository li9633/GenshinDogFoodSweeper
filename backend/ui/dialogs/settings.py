"""
设置对话框
==========
提供截图区域、延迟参数、匹配阈值等配置项。
通过 API 层读取/保存设置，不直接操作数据库。
"""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QSpinBox,
    QVBoxLayout,
)


class SettingsDialog(QDialog):
    """设置对话框"""

    settings_changed = pyqtSignal(dict)  # 设置变更时发出

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setMinimumWidth(420)
        self._build_ui()
        self._load_settings()

    # ---------- UI 构建 ----------

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # --- 截图设置 ---
        group_capture = QGroupBox("截图设置")
        form_capture = QFormLayout()
        form_capture.setSpacing(12)

        self._spin_capture_delay = QSpinBox()
        self._spin_capture_delay.setRange(100, 5000)
        self._spin_capture_delay.setSuffix(" ms")
        self._spin_capture_delay.setToolTip("每次截图之间的延迟")
        form_capture.addRow("截图间隔:", self._spin_capture_delay)

        self._check_background_capture = QCheckBox(
            "允许后台截图（窗口被遮挡时仍可截图）"
        )
        self._check_background_capture.setChecked(True)
        form_capture.addRow(self._check_background_capture)

        group_capture.setLayout(form_capture)
        layout.addWidget(group_capture)

        # --- 识别设置 ---
        group_recognize = QGroupBox("识别设置")
        form_recognize = QFormLayout()
        form_recognize.setSpacing(12)

        self._spin_match_threshold = QDoubleSpinBox()
        self._spin_match_threshold.setRange(0.50, 0.99)
        self._spin_match_threshold.setSingleStep(0.01)
        self._spin_match_threshold.setDecimals(2)
        self._spin_match_threshold.setToolTip("模板匹配阈值，越高越严格")
        form_recognize.addRow("匹配阈值:", self._spin_match_threshold)

        self._spin_ocr_confidence = QDoubleSpinBox()
        self._spin_ocr_confidence.setRange(0.50, 0.99)
        self._spin_ocr_confidence.setSingleStep(0.01)
        self._spin_ocr_confidence.setDecimals(2)
        self._spin_ocr_confidence.setToolTip("OCR 置信度阈值")
        form_recognize.addRow("OCR 置信度:", self._spin_ocr_confidence)

        group_recognize.setLayout(form_recognize)
        layout.addWidget(group_recognize)

        # --- 自动化设置 ---
        group_auto = QGroupBox("自动化设置")
        form_auto = QFormLayout()
        form_auto.setSpacing(12)

        self._spin_action_delay = QSpinBox()
        self._spin_action_delay.setRange(100, 3000)
        self._spin_action_delay.setSuffix(" ms")
        self._spin_action_delay.setToolTip("每次键鼠操作之间的延迟")
        form_auto.addRow("操作间隔:", self._spin_action_delay)

        self._check_random_delay = QCheckBox("启用随机延迟（模拟真人操作）")
        self._check_random_delay.setChecked(True)
        form_auto.addRow(self._check_random_delay)

        self._spin_max_artifacts = QSpinBox()
        self._spin_max_artifacts.setRange(1, 1500)
        self._spin_max_artifacts.setToolTip("单次扫描最多处理的圣遗物数量")
        form_auto.addRow("单次上限:", self._spin_max_artifacts)

        group_auto.setLayout(form_auto)
        layout.addWidget(group_auto)

        # --- 按钮 ---
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Apply
        )
        btn_box.accepted.connect(self._on_accept)
        btn_box.rejected.connect(self.reject)
        btn_box.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(
            self._on_apply
        )
        ok_btn = btn_box.button(QDialogButtonBox.StandardButton.Ok)
        if ok_btn:
            ok_btn.setProperty("class", "primary")
        layout.addWidget(btn_box)

    # ---------- 设置读写 ----------

    def _load_settings(self):
        """从 API 层加载当前设置"""
        # TODO: 接入 API 层后改为 HTTP 调用
        # GET /api/settings → 填充各控件
        defaults = {
            "capture_delay": 500,
            "background_capture": True,
            "match_threshold": 0.85,
            "ocr_confidence": 0.80,
            "action_delay": 300,
            "random_delay": True,
            "max_artifacts": 500,
        }
        self._spin_capture_delay.setValue(defaults["capture_delay"])
        self._check_background_capture.setChecked(defaults["background_capture"])
        self._spin_match_threshold.setValue(defaults["match_threshold"])
        self._spin_ocr_confidence.setValue(defaults["ocr_confidence"])
        self._spin_action_delay.setValue(defaults["action_delay"])
        self._check_random_delay.setChecked(defaults["random_delay"])
        self._spin_max_artifacts.setValue(defaults["max_artifacts"])

    def _collect_settings(self) -> dict:
        """收集当前 UI 控件值"""
        return {
            "capture_delay": self._spin_capture_delay.value(),
            "background_capture": self._check_background_capture.isChecked(),
            "match_threshold": self._spin_match_threshold.value(),
            "ocr_confidence": self._spin_ocr_confidence.value(),
            "action_delay": self._spin_action_delay.value(),
            "random_delay": self._check_random_delay.isChecked(),
            "max_artifacts": self._spin_max_artifacts.value(),
        }

    def _on_apply(self):
        """应用设置"""
        settings = self._collect_settings()
        # TODO: PUT /api/settings
        self.settings_changed.emit(settings)

    def _on_accept(self):
        """确定并关闭"""
        self._on_apply()
        self.accept()