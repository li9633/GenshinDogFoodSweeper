"""GitHub Release API 模拟器（GUI）
=================================
使用本地 HTTP Server 模拟 GitHub Release API，通过 GUI 控制场景，
方便调试 AppUpdater 更新流程。

功能：
- 启动/停止 Mock GitHub API 服务器
- 预设场景切换（有新版本 / 同版本 / 无资产 / 版本异常 / 自定义）
- 错误模拟（200 / 500 / 超时）
- 一键批量测试所有场景组合
- 真实文件下载模拟 + 限速
- 实时请求日志

用法:
    cd D:/MyCodeProject/GenshinDogFoodSweeper
    uv run python simulators/update_gui.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.paths import ROOT

sys.path.insert(0, str(ROOT / "backend"))

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from backend.features.update.app_updater import UPDATE_OWNER, UPDATE_REPO, AppUpdater
from common.datetime_helper import FMT_TIME, DateTimeHelper
from tests.mocks.mock_github_api import (
    CURRENT_MAJOR,
    CURRENT_MINOR,
    CURRENT_PATCH,
    SCENARIO_500_LABELS,
    SCENARIO_LABELS,
    MockGitHubServer,
)

# # Worker: 异步执行 AppUpdater.check()，避免阻塞 GUI 线程
#

class CheckWorker(QThread):
    """在子线程执行 AppUpdater.check()"""
    finished = Signal(dict)

    def __init__(self, api_base: str, scenario_name: str, error_name: str):
        super().__init__()
        self._api_base = api_base
        self._scenario_name = scenario_name
        self._error_name = error_name

    def run(self) -> None:
        t0 = time.perf_counter()
        updater = AppUpdater(
            owner=UPDATE_OWNER, repo=UPDATE_REPO, api_base=self._api_base,
        )
        try:
            result = updater.check()
            if result:
                has_update, _info, error = updater.is_update_available()
                elapsed = (time.perf_counter() - t0) * 1000
                self.finished.emit({
                    "scenario": self._scenario_name,
                    "error_scenario": self._error_name,
                    "success": True,
                    "tag": result["tag"],
                    "size": result["size"],
                    "has_update": has_update,
                    "info_msg": error if error else ("有更新" if has_update else "已是最新"),
                    "elapsed_ms": elapsed,
                })
            else:
                elapsed = (time.perf_counter() - t0) * 1000
                self.finished.emit({
                    "scenario": self._scenario_name,
                    "error_scenario": self._error_name,
                    "success": True,
                    "tag": None,
                    "size": None,
                    "has_update": None,
                    "info_msg": "无 .exe 资产",
                    "elapsed_ms": elapsed,
                })
        except Exception as e:
            elapsed = (time.perf_counter() - t0) * 1000
            self.finished.emit({
                "scenario": self._scenario_name,
                "error_scenario": self._error_name,
                "success": False,
                "tag": None,
                "size": None,
                "has_update": None,
                "info_msg": f"{type(e).__name__}: {e}",
                "elapsed_ms": elapsed,
            })


# # 主窗口
#

class MockApiWindow(QWidget):
    def __init__(self):
        super().__init__()
        self._server = MockGitHubServer(port=9888)
        self._server.set_log_callback(self._on_log)
        self._pending_logs: list[str] = []
        self._updater: AppUpdater | None = None
        self._check_workers: list[CheckWorker] = []

        self.setWindowTitle("GitHub Release API 模拟器")
        self.setMinimumSize(800, 600)
        self.resize(850, 720)

        self._setup_ui()
        self._refresh_state()

        self._log_timer = QTimer(self)
        self._log_timer.setInterval(100)
        self._log_timer.timeout.connect(self._flush_logs)
        self._log_timer.start()

    # # UI 构建
    #

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(8)

        mono_font = QFont("Consolas", 10)

        # ── 第1行：服务器控制 ──
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

        self._health_btn = QPushButton("健康检查")
        self._health_btn.clicked.connect(self._health_check)
        self._health_btn.setEnabled(False)
        self._health_btn.setToolTip("验证 mock 服务器是否正常响应 /health")
        server_grid.addWidget(self._health_btn, 0, 4)

        self._copy_url_btn = QPushButton("复制 API 地址")
        self._copy_url_btn.clicked.connect(self._copy_api_url)
        self._copy_url_btn.setEnabled(False)
        server_grid.addWidget(self._copy_url_btn, 0, 5)

        main_layout.addWidget(server_group)

        # ── 第2行：场景控制 ──
        ctrl_group = QGroupBox("场景控制")
        ctrl_grid = QGridLayout(ctrl_group)

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

        self._batch_btn = QPushButton("批量测试全部场景")
        self._batch_btn.clicked.connect(self._batch_test)
        self._batch_btn.setEnabled(False)
        self._batch_btn.setToolTip("遍历 场景×错误 所有组合并展示结果")
        ctrl_grid.addWidget(self._batch_btn, 0, 5)

        self._reset_json_btn = QPushButton("重置 JSON")
        self._reset_json_btn.clicked.connect(self._reset_json_to_current_scenario)
        self._reset_json_btn.setToolTip("丢弃自定义编辑，恢复当前预设场景的原始 JSON")
        ctrl_grid.addWidget(self._reset_json_btn, 1, 1)

        main_layout.addWidget(ctrl_group)

        # ── 第3行：Release JSON 编辑器 ──
        json_group = QGroupBox("Release JSON")
        json_layout = QVBoxLayout(json_group)

        json_header = QHBoxLayout()
        self._json_status = QLabel("")
        self._json_status.setStyleSheet("color: #888;")
        json_header.addWidget(self._json_status)
        json_header.addStretch()
        self._format_json_btn = QPushButton("格式化")
        self._format_json_btn.clicked.connect(self._format_json)
        self._format_json_btn.setFixedWidth(80)
        json_header.addWidget(self._format_json_btn)
        json_layout.addLayout(json_header)

        self._json_edit = QPlainTextEdit()
        self._json_edit.setFont(mono_font)
        self._json_edit.setMaximumHeight(220)
        self._json_edit.textChanged.connect(self._on_json_changed)
        json_layout.addWidget(self._json_edit)
        main_layout.addWidget(json_group)

        # ── 第4行：下载配置 ──
        dl_group = QGroupBox("下载配置（真实文件服务 & 限速）")
        dl_grid = QGridLayout(dl_group)

        dl_grid.addWidget(QLabel("安装包:"), 0, 0)
        self._file_label = QLabel("（未选择，将返回假数据）")
        self._file_label.setStyleSheet("color: #888;")
        dl_grid.addWidget(self._file_label, 0, 1)
        self._pick_file_btn = QPushButton("选择文件...")
        self._pick_file_btn.clicked.connect(self._pick_download_file)
        dl_grid.addWidget(self._pick_file_btn, 0, 2)
        self._clear_file_btn = QPushButton("清除")
        self._clear_file_btn.clicked.connect(self._clear_download_file)
        self._clear_file_btn.setFixedWidth(60)
        dl_grid.addWidget(self._clear_file_btn, 0, 3)

        dl_grid.addWidget(QLabel("限速:"), 1, 0)
        self._bw_spin = QSpinBox()
        self._bw_spin.setRange(0, 102400)
        self._bw_spin.setValue(0)
        self._bw_spin.setSuffix(" KB/s")
        self._bw_spin.setSpecialValueText("0 = 不限速")
        self._bw_spin.setToolTip("模拟真实网络速度，0 为不限速。例如 1024 KB/s ≈ 1 MB/s")
        self._bw_spin.valueChanged.connect(self._on_bandwidth_changed)
        dl_grid.addWidget(self._bw_spin, 1, 1)

        main_layout.addWidget(dl_group)

        # ── 第5行：标签页（日志 / 批量测试结果） ──
        tabs = QTabWidget()

        # 日志页
        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        log_layout.setContentsMargins(0, 0, 0, 0)
        self._log_edit = QPlainTextEdit()
        self._log_edit.setFont(mono_font)
        self._log_edit.setReadOnly(True)
        self._log_edit.setStyleSheet(
            "QPlainTextEdit { background-color: #1e1e1e; color: #0f0; }"
        )
        log_layout.addWidget(self._log_edit)
        clear_btn = QPushButton("清空日志")
        clear_btn.clicked.connect(self._clear_log)
        clear_btn.setFixedWidth(80)
        log_layout.addWidget(clear_btn, alignment=Qt.AlignmentFlag.AlignRight)
        tabs.addTab(log_widget, "请求日志")

        # 批量测试结果页
        batch_widget = QWidget()
        batch_layout = QVBoxLayout(batch_widget)
        batch_layout.setContentsMargins(0, 0, 0, 0)
        self._batch_table = QTableWidget(0, 5)
        self._batch_table.setHorizontalHeaderLabels(
            ["场景", "错误模拟", "结果", "详情", "耗时"]
        )
        self._batch_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._batch_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self._batch_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        batch_layout.addWidget(self._batch_table)

        clear_batch_btn = QPushButton("清空结果")
        clear_batch_btn.clicked.connect(self._clear_batch_results)
        clear_batch_btn.setFixedWidth(80)
        batch_layout.addWidget(
            clear_batch_btn, alignment=Qt.AlignmentFlag.AlignRight
        )
        tabs.addTab(batch_widget, "批量测试结果")
        main_layout.addWidget(tabs, 1)

        # ── 第6行：版本信息 ──
        info_label = QLabel(
            f"当前 App 版本: v{CURRENT_MAJOR}.{CURRENT_MINOR}.{CURRENT_PATCH}"
            f"  |  {UPDATE_OWNER}/{UPDATE_REPO}"
            f"  |  mock API: http://127.0.0.1:{self._server.port}"
            f"/repos/{{owner}}/{{repo}}/releases/latest"
        )
        info_label.setStyleSheet("color: #888;")
        main_layout.addWidget(info_label)

    # # 事件处理 — 服务器
    #

    def _toggle_server(self) -> None:
        if self._server.is_running:
            self._server.stop()
            self._updater = None
        else:
            port = self._port_spin.value()
            if port != self._server.port:
                saved_state = self._capture_server_state()
                self._server = MockGitHubServer(port=port)
                self._server.set_log_callback(self._on_log)
                self._restore_server_state(saved_state)
                self._sync_ui_to_server_state(saved_state)
            ok = self._server.start()
            if not ok:
                self._append_log(f"[{self._ts()}] ⚠ 端口 {port} 被占用，启动失败")
                return
            self._updater = AppUpdater(
                owner=UPDATE_OWNER, repo=UPDATE_REPO,
                api_base=self._server.api_url,
            )
        self._refresh_state()

    def _capture_server_state(self) -> dict:
        return {
            "download_file_path": self._server.download_file_path,
            "bandwidth_limit": self._server.bandwidth_limit,
            "current_scenario": self._server.current_scenario,
            "error_scenario": self._server.error_scenario,
            "custom_release": self._server.get_current_release()
            if self._server.current_scenario == "custom"
            else None,
        }

    def _restore_server_state(self, state: dict) -> None:
        self._server.download_file_path = state["download_file_path"]
        self._server.bandwidth_limit = state["bandwidth_limit"]
        self._server.set_error_scenario(state["error_scenario"])
        if state["custom_release"] and state["current_scenario"] == "custom":
            self._server.set_custom_release(state["custom_release"])
        self._server.set_scenario(state["current_scenario"])

    def _sync_ui_to_server_state(self, state: dict) -> None:
        self._scenario_combo.blockSignals(True)
        idx = self._scenario_combo.findData(state["current_scenario"])
        if idx >= 0:
            self._scenario_combo.setCurrentIndex(idx)
        self._scenario_combo.blockSignals(False)

        self._error_combo.blockSignals(True)
        idx = self._error_combo.findData(state["error_scenario"])
        if idx >= 0:
            self._error_combo.setCurrentIndex(idx)
        self._error_combo.blockSignals(False)

    def _health_check(self) -> None:
        import urllib.request

        url = f"{self._server.base_url}/health"
        self._append_log(f"[{self._ts()}] GET {url}")
        try:
            req = urllib.request.Request(url)
            resp = urllib.request.urlopen(req, timeout=3)
            data = json.loads(resp.read().decode())
            header_ok = resp.headers.get("X-GenshinDogFood-Mock") == "true"
            body_ok = data.get("mock_github_api") is True
            if header_ok and body_ok:
                self._append_log(
                    f"[{self._ts()}] ✓ 健康检查通过 "
                    f"(Header={header_ok}, Body={body_ok})"
                )
            else:
                self._append_log(
                    f"[{self._ts()}] ✗ 签名验证失败 "
                    f"(Header={header_ok}, Body={body_ok})"
                )
        except Exception as e:
            self._append_log(
                f"[{self._ts()}] ✗ 健康检查失败: {type(e).__name__}: {e}"
            )

    def _refresh_state(self) -> None:
        running = self._server.is_running
        if running:
            self._status_label.setText("● 运行中")
            self._status_label.setStyleSheet(
                "color: #4CAF50; font-weight: bold;"
            )
            self._start_btn.setText("停止服务器")
            self._start_btn.setStyleSheet(
                "QPushButton { background-color: #D32F2F; color: white; }"
            )
        else:
            self._status_label.setText("● 已停止")
            self._status_label.setStyleSheet("color: #888;")
            self._start_btn.setText("启动服务器")
            self._start_btn.setStyleSheet("")

        self._port_spin.setEnabled(not running)
        self._health_btn.setEnabled(running)
        self._copy_url_btn.setEnabled(running)
        self._test_btn.setEnabled(running)
        self._batch_btn.setEnabled(running)

        if running:
            self._update_json_display()

    # # 事件处理 — 场景
    #

    def _on_scenario_changed(self, idx: int) -> None:
        key = self._scenario_combo.itemData(idx)
        self._server.set_scenario(key)
        self._update_json_display()

    def _on_error_changed(self, idx: int) -> None:
        key = self._error_combo.itemData(idx)
        self._server.set_error_scenario(key)

    def _update_json_display(self) -> None:
        self._json_edit.blockSignals(True)
        self._json_edit.setPlainText(
            json.dumps(
                self._server.get_current_release(),
                ensure_ascii=False,
                indent=2,
            )
        )
        self._json_edit.blockSignals(False)
        self._validate_json()

    def _reset_json_to_current_scenario(self) -> None:
        key = self._scenario_combo.currentData()
        self._server.set_scenario(key)
        self._update_json_display()
        self._json_status.setText("已重置为预设")
        self._json_status.setStyleSheet("color: #2196F3;")

    def _on_json_changed(self) -> None:
        if not self._server.is_running:
            return
        self._validate_json()

    def _validate_json(self) -> None:
        text = self._json_edit.toPlainText().strip()
        if not text:
            self._json_status.setText("")
            self._json_status.setStyleSheet("")
            return
        try:
            data = json.loads(text)
            self._server.set_custom_release(data)
            if self._scenario_combo.currentData() != "custom":
                self._scenario_combo.blockSignals(True)
                self._scenario_combo.setCurrentIndex(
                    self._scenario_combo.findData("custom")
                )
                self._scenario_combo.blockSignals(False)
                self._server.set_scenario("custom")
            self._json_status.setText("✓ JSON 有效（已应用为自定义场景）")
            self._json_status.setStyleSheet("color: #4CAF50;")
        except json.JSONDecodeError as e:
            self._json_status.setText(f"✗ JSON 格式错误: {e}")
            self._json_status.setStyleSheet("color: #F44336;")

    def _format_json(self) -> None:
        text = self._json_edit.toPlainText().strip()
        try:
            data = json.loads(text)
            formatted = json.dumps(data, ensure_ascii=False, indent=2)
            self._json_edit.setPlainText(formatted)
        except json.JSONDecodeError:
            pass

    # # 事件处理 — 日志
    #

    @staticmethod
    def _ts() -> str:
        return DateTimeHelper.now().strftime(FMT_TIME)

    def _on_log(self, entry: str) -> None:
        self._pending_logs.append(f"[{self._ts()}] {entry}")

    def _flush_logs(self) -> None:
        if not self._pending_logs:
            return
        pending, self._pending_logs = self._pending_logs, []
        chunk_size = 50
        for i in range(0, len(pending), chunk_size):
            chunk = pending[i:i + chunk_size]
            self._log_edit.appendPlainText("\n".join(chunk))
        scrollbar = self._log_edit.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _append_log(self, msg: str) -> None:
        self._log_edit.appendPlainText(msg)
        scrollbar = self._log_edit.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _clear_log(self) -> None:
        self._pending_logs.clear()
        self._log_edit.clear()

    def _copy_api_url(self) -> None:
        QApplication.clipboard().setText(
            f"{self._server.base_url}/repos/{{owner}}/{{repo}}/releases/latest"
        )
        self._append_log(f"[{self._ts()}] 📋 API 地址已复制到剪贴板")

    # # 事件处理 — 下载配置
    #

    def _pick_download_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选择安装包文件", "",
            "安装程序 (*.exe);;所有文件 (*)",
        )
        if not path:
            return
        file_path = Path(path)
        file_size = file_path.stat().st_size
        self._server.download_file_path = str(file_path)
        self._file_label.setText(file_path.name)
        self._file_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
        file_size_mb = file_size / (1024 * 1024)
        self._append_log(
            f"[{self._ts()}] 📁 下载文件已设置: "
            f"{file_path.name} ({file_size_mb:.1f} MB)"
        )

        release = self._server.get_current_release()
        if release and release.get("assets"):
            asset = release["assets"][0]
            asset["name"] = file_path.name
            asset["size"] = file_size
            asset["browser_download_url"] = (
                f"{self._server.base_url}/download/{file_path.name}"
            )
            self._server.set_custom_release(release)
            self._server.set_scenario("custom")
            self._scenario_combo.blockSignals(True)
            self._scenario_combo.setCurrentIndex(
                self._scenario_combo.findData("custom")
            )
            self._scenario_combo.blockSignals(False)

        self._update_json_display()

    def _clear_download_file(self) -> None:
        self._server.download_file_path = None
        self._file_label.setText("（未选择，将返回假数据）")
        self._file_label.setStyleSheet("color: #888;")
        self._append_log(f"[{self._ts()}] 📁 下载文件已清除，恢复假数据模式")

    def _on_bandwidth_changed(self, value: int) -> None:
        self._server.bandwidth_limit = value * 1024

    # # 事件处理 — 更新检查（异步）
    #

    def _test_update_check(self) -> None:
        if not self._server.is_running:
            return
        scenario_name = self._scenario_combo.currentData()
        error_name = self._error_combo.currentData()
        self._append_log(
            f"[{self._ts()}] ── 执行更新检查 "
            f"({SCENARIO_LABELS[scenario_name]} + {SCENARIO_500_LABELS[error_name]}) ──"
        )

        worker = CheckWorker(self._server.api_url, scenario_name, error_name)
        worker.finished.connect(self._on_single_check_done)
        self._check_workers.append(worker)
        self._test_btn.setEnabled(False)
        self._test_btn.setText("检查中...")
        worker.start()

    def _on_single_check_done(self, result: dict) -> None:
        self._test_btn.setEnabled(True)
        self._test_btn.setText("测试更新检查")

        if result["success"]:
            tag_info = f"tag={result['tag']}" if result["tag"] else "无资产"
            self._append_log(
                f"[{self._ts()}] ✓ {tag_info}, "
                f"{result['info_msg']}, "
                f"耗时 {result['elapsed_ms']:.0f}ms"
            )
        else:
            self._append_log(
                f"[{self._ts()}] ✗ 失败: {result['info_msg']}, "
                f"耗时 {result['elapsed_ms']:.0f}ms"
            )

    # ── 批量测试 ──

    def _batch_test(self) -> None:
        if not self._server.is_running:
            return
        self._clear_batch_results()
        self._append_log(f"[{self._ts()}] ⚡ 开始批量测试全部场景...")

        scenarios = list(SCENARIO_LABELS.keys())
        errors = list(SCENARIO_500_LABELS.keys())
        self._batch_total = len(scenarios) * len(errors)
        self._batch_done = 0
        self._batch_btn.setEnabled(False)
        self._batch_btn.setText(f"测试中 0/{self._batch_total}...")

        api_base = self._server.api_url

        for sc in scenarios:
            for er in errors:
                self._server.set_scenario(sc)
                self._server.set_error_scenario(er)
                worker = CheckWorker(api_base, sc, er)
                worker.finished.connect(self._on_batch_check_done)
                self._check_workers.append(worker)
                worker.start()

    def _on_batch_check_done(self, result: dict) -> None:
        row = self._batch_table.rowCount()
        self._batch_table.insertRow(row)

        item_sc = QTableWidgetItem(SCENARIO_LABELS.get(
            result["scenario"], result["scenario"]
        ))
        self._batch_table.setItem(row, 0, item_sc)

        item_err = QTableWidgetItem(SCENARIO_500_LABELS.get(
            result["error_scenario"], result["error_scenario"]
        ))
        self._batch_table.setItem(row, 1, item_err)

        if result["success"]:
            item_result = QTableWidgetItem("✓ 成功")
            item_result.setForeground(Qt.GlobalColor.darkGreen)
        else:
            item_result = QTableWidgetItem("✗ 失败")
            item_result.setForeground(Qt.GlobalColor.red)
        self._batch_table.setItem(row, 2, item_result)

        item_detail = QTableWidgetItem(result["info_msg"] or "")
        self._batch_table.setItem(row, 3, item_detail)

        item_time = QTableWidgetItem(f"{result['elapsed_ms']:.0f}ms")
        self._batch_table.setItem(row, 4, item_time)

        self._batch_done += 1
        self._batch_btn.setText(
            f"测试中 {self._batch_done}/{self._batch_total}..."
        )

        if self._batch_done >= self._batch_total:
            self._batch_btn.setEnabled(True)
            self._batch_btn.setText("批量测试全部场景")
            self._append_log(
                f"[{self._ts()}] ✓ 批量测试完成 "
                f"({self._batch_total} 个场景组合)"
            )
            self._server.set_scenario(self._scenario_combo.currentData())
            self._server.set_error_scenario(self._error_combo.currentData())

    def _clear_batch_results(self) -> None:
        self._batch_table.setRowCount(0)

    # # 生命周期
    #

    def closeEvent(self, event) -> None:
        for w in self._check_workers:
            if w.isRunning():
                w.quit()
                w.wait(2000)
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