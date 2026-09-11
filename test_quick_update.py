r"""GitHub Release API 模拟器（GUI）
=================================
使用本地 HTTP Server 模拟 GitHub Release API，通过 GUI 控制场景，
方便调试 AppUpdater 更新流程。

用法:
    cd D:\MyCodeProject\GenshinDogFoodSweeper
    uv run python test_quick_update.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
_BACKEND_DIR = _PROJECT_ROOT / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QGridLayout,
    QGroupBox,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from backend.utils.app_updater import AppUpdater
from backend.utils.mock_github_api import (
    CURRENT_MAJOR,
    CURRENT_MINOR,
    CURRENT_PATCH,
    SCENARIO_500_LABELS,
    SCENARIO_LABELS,
    MockGitHubServer,
)


class MockApiWindow(QWidget):
    def __init__(self):
        super().__init__()
        self._server = MockGitHubServer(port=9888)
        self._server.set_log_callback(self._on_log)
        self._log_buffer: list[str] = []
        self._updater: AppUpdater | None = None

        self.setWindowTitle("GitHub Release API 模拟器")
        self.setMinimumSize(600, 500)
        self.resize(650, 580)

        self._setup_ui()
        self._refresh_state()

    # ============================================================
    # UI 构建
    # ============================================================

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        font = QFont("Consolas", 10)

        # ---- 第1行：服务器控制 ----
        server_group = QGroupBox("服务器控制")
        server_grid = QGridLayout(server_group)

        server_grid.addWidget(QLabel("端口:"), 0, 0)
        self._port_spin = QSpinBox()
        self._port_spin.setRange(1024, 65535)
        self._port_spin.setValue(9888)
        self._port_spin.setFixedWidth(80)
        server_grid.addWidget(self._port_spin, 0, 1)

        self._status_label = QLabel("● 已停止")
        self._status_label.setStyleSheet("color: #888;")
        server_grid.addWidget(self._status_label, 0, 2)

        self._start_btn = QPushButton("启动服务器")
        self._start_btn.clicked.connect(self._toggle_server)
        server_grid.addWidget(self._start_btn, 0, 3)

        self._copy_url_btn = QPushButton("复制 API 地址")
        self._copy_url_btn.clicked.connect(self._copy_api_url)
        self._copy_url_btn.setEnabled(False)
        server_grid.addWidget(self._copy_url_btn, 0, 4)

        layout.addWidget(server_group)

        # ---- 第2行：场景控制 ----
        ctrl_grid = QGridLayout()

        ctrl_grid.addWidget(QLabel("Release 场景:"), 0, 0)
        self._scenario_combo = QComboBox()
        for key, label in SCENARIO_LABELS.items():
            self._scenario_combo.addItem(label, key)
        self._scenario_combo.currentIndexChanged.connect(self._on_scenario_changed)
        ctrl_grid.addWidget(self._scenario_combo, 0, 1)

        ctrl_grid.addWidget(QLabel("错误模拟:"), 0, 2)
        self._error_combo = QComboBox()
        for key, label in SCENARIO_500_LABELS.items():
            self._error_combo.addItem(label, key)
        self._error_combo.currentIndexChanged.connect(self._on_error_changed)
        ctrl_grid.addWidget(self._error_combo, 0, 3)

        self._test_btn = QPushButton("测试更新检查")
        self._test_btn.clicked.connect(self._test_update_check)
        self._test_btn.setEnabled(False)
        ctrl_grid.addWidget(self._test_btn, 0, 4)

        layout.addLayout(ctrl_grid)

        # ---- 第3行：Release JSON 编辑 ----
        json_group = QGroupBox("Release JSON（双击预设场景可编辑）")
        json_layout = QVBoxLayout(json_group)
        self._json_edit = QPlainTextEdit()
        self._json_edit.setFont(font)
        self._json_edit.setMaximumHeight(180)
        self._json_edit.textChanged.connect(self._on_json_changed)
        json_layout.addWidget(self._json_edit)
        layout.addWidget(json_group)

        # ---- 第4行：请求日志 ----
        log_group = QGroupBox("请求日志")
        log_layout = QVBoxLayout(log_group)
        self._log_edit = QPlainTextEdit()
        self._log_edit.setFont(font)
        self._log_edit.setReadOnly(True)
        self._log_edit.setStyleSheet("QPlainTextEdit { background-color: #1e1e1e; color: #0f0; }")
        log_layout.addWidget(self._log_edit)

        clear_btn = QPushButton("清空日志")
        clear_btn.clicked.connect(self._clear_log)
        clear_btn.setFixedWidth(80)
        log_layout.addWidget(clear_btn, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addWidget(log_group)

        # ---- 第5行：当前版本信息 ----
        info_label = QLabel(
            f"当前 App 版本: v{CURRENT_MAJOR}.{CURRENT_MINOR}.{CURRENT_PATCH}  |  "
            f"mock API: http://127.0.0.1:{self._server.port}/repos/{{owner}}/{{repo}}/releases/latest"
        )
        info_label.setStyleSheet("color: #888;")
        layout.addWidget(info_label)

    # ============================================================
    # 事件处理
    # ============================================================

    def _toggle_server(self) -> None:
        if self._server.is_running:
            self._server.stop()
            self._updater = None
        else:
            port = self._port_spin.value()
            if port != self._server.port:
                self._server = MockGitHubServer(port=port)
                self._server.set_log_callback(self._on_log)
            ok = self._server.start()
            if not ok:
                self._append_log(f"⚠ 端口 {port} 被占用，启动失败")
                return
            self._updater = AppUpdater(owner="test-owner", repo="test-repo", api_base=self._server.api_url)
        self._refresh_state()

    def _refresh_state(self) -> None:
        running = self._server.is_running
        if running:
            self._status_label.setText("● 运行中")
            self._status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
            self._start_btn.setText("停止服务器")
            self._start_btn.setStyleSheet("QPushButton { background-color: #D32F2F; color: white; }")
        else:
            self._status_label.setText("● 已停止")
            self._status_label.setStyleSheet("color: #888;")
            self._start_btn.setText("启动服务器")
            self._start_btn.setStyleSheet("")

        self._port_spin.setEnabled(not running)
        self._copy_url_btn.setEnabled(running)
        self._test_btn.setEnabled(running)

        if running:
            self._json_edit.setPlainText(
                json.dumps(self._server.get_current_release(), ensure_ascii=False, indent=2)
            )

    def _on_scenario_changed(self, idx: int) -> None:
        key = self._scenario_combo.itemData(idx)
        self._server.set_scenario(key)
        self._json_edit.setPlainText(
            json.dumps(self._server.get_current_release(), ensure_ascii=False, indent=2)
        )

    def _on_error_changed(self, idx: int) -> None:
        key = self._error_combo.itemData(idx)
        self._server.set_error_scenario(key)

    def _on_json_changed(self) -> None:
        if not self._server.is_running:
            return
        try:
            data = json.loads(self._json_edit.toPlainText())
            self._server.set_custom_release(data)
            if self._scenario_combo.currentData() != "custom":
                self._scenario_combo.blockSignals(True)
                self._scenario_combo.setCurrentIndex(
                    self._scenario_combo.findData("custom")
                )
                self._scenario_combo.blockSignals(False)
        except json.JSONDecodeError:
            pass

    def _on_log(self, entry: str) -> None:
        self._log_edit.appendPlainText(entry)

    def _append_log(self, msg: str) -> None:
        self._log_edit.appendPlainText(msg)

    def _clear_log(self) -> None:
        self._log_edit.clear()

    def _copy_api_url(self) -> None:
        QApplication.clipboard().setText(
            f"{self._server.base_url}/repos/{{owner}}/{{repo}}/releases/latest"
        )
        self._append_log("📋 API 地址已复制到剪贴板")

    def _test_update_check(self) -> None:
        if not self._updater:
            return
        self._append_log("── 执行更新检查 ──")
        try:
            result = self._updater.check()
            if result:
                has_update, info, error = self._updater.is_update_available()
                self._append_log(f"check() → tag={result['tag']}, size={result['size']}")
                if error:
                    self._append_log(f"is_update_available() → error={error}")
                else:
                    self._append_log(f"is_update_available() → has_update={has_update}, info={info is not None}")
            else:
                self._append_log("check() → None（Release 中没有 .exe 资产）")
        except Exception as e:
            self._append_log(f"检查异常: {e}")

    def closeEvent(self, event) -> None:
        self._server.stop()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MockApiWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()