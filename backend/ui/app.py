"""
应用主入口
==========
负责：QApplication 初始化、托盘管理、FastAPI 服务启动、信号连接。
"""

from __future__ import annotations

import threading
import webbrowser

from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from PyQt6.QtWidgets import QApplication

from .dialogs.settings import SettingsDialog
from .main_window import MainWindow
from .tray import TrayManager
from .widgets.capture_view import CapturePreviewWidget


class GenshinApp(QObject):
    """主应用控制器（非 GUI 组件，负责协调各层）"""

    # 信号
    server_started = pyqtSignal(int)  # 端口号
    server_stopped = pyqtSignal()
    scan_status_changed = pyqtSignal(bool)  # True=扫描中

    PANEL_URL = "http://127.0.0.1:8765"
    SERVER_PORT = 8765

    def __init__(self, qapp: QApplication):
        super().__init__()
        self._qapp = qapp
        self._scanning = False
        self._server_thread: threading.Thread | None = None
        self._settings_dialog: SettingsDialog | None = None
        self._capture_widget: CapturePreviewWidget | None = None
        self._main_window: MainWindow | None = None

        # 主窗口
        self._main_window = MainWindow()
        self._main_window.set_capture_preview(self._create_capture_widget())
        self._main_window.scan_requested.connect(self._on_start_scan)
        self._main_window.stop_requested.connect(self._on_stop_scan)
        self._main_window.closed.connect(self._on_main_window_closed)
        self._main_window.show()

        # 托盘
        self._tray = TrayManager()
        self._connect_tray_signals()

        # 启动后端服务
        self._start_backend_server()

        # 启动托盘提示
        QTimer.singleShot(500, lambda: self._tray.show_message(
            "原神狗粮清扫器", "已在后台运行，右键托盘图标操作"
        ))

    # ---------- 生命周期 ----------

    def run(self):
        """进入事件循环"""
        self._qapp.exec()

    def shutdown(self):
        """清理资源"""
        self._stop_backend_server()
        self._qapp.quit()

    # ---------- 信号连接 ----------

    def _connect_tray_signals(self):
        self._tray.scan_requested.connect(self._on_start_scan)
        self._tray.stop_requested.connect(self._on_stop_scan)
        self._tray.panel_requested.connect(self._open_browser)
        self._tray.settings_requested.connect(self._open_settings)
        self._tray.exit_requested.connect(self.shutdown)

    # ---------- 后端服务 ----------

    def _start_backend_server(self):
        """在后台线程启动 FastAPI/Uvicorn"""

        def run_server():
            import uvicorn

            try:
                uvicorn.run(
                    "backend.server:app",
                    host="127.0.0.1",
                    port=self.SERVER_PORT,
                    log_config=None,  # 禁用 uvicorn 自带日志配置
                )
            except (OSError, SystemExit) as e:
                from utils.logger import log
                log.error(f"服务器启动失败: {e}")

        self._server_thread = threading.Thread(target=run_server, daemon=True)
        self._server_thread.start()
        self.server_started.emit(self.SERVER_PORT)

        from utils.logger import log
        log.info(f"后端服务已启动 → {self.PANEL_URL}")

    def _stop_backend_server(self):
        """停止后端服务"""
        # daemon 线程会自动结束
        self.server_stopped.emit()

    # ---------- 扫描控制 ----------

    def _on_start_scan(self):
        """开始扫描"""
        # TODO: 调用 API POST /api/scan/start
        self._scanning = True
        self._tray.set_scanning(True)
        self.scan_status_changed.emit(True)
        self._tray.show_message("扫描", "已开始扫描圣遗物…")

    def _on_stop_scan(self):
        """停止扫描"""
        # TODO: 调用 API POST /api/scan/stop
        self._scanning = False
        self._tray.set_scanning(False)
        self.scan_status_changed.emit(False)
        self._tray.show_message("扫描", "扫描已停止")

    # ---------- 面板 & 设置 ----------

    def _open_browser(self):
        """打开 Web 管理面板"""
        webbrowser.open(self.PANEL_URL)

    def _open_settings(self):
        """打开设置对话框"""
        if self._settings_dialog is None:
            self._settings_dialog = SettingsDialog()
            self._settings_dialog.settings_changed.connect(self._on_settings_changed)
        self._settings_dialog.show()
        self._settings_dialog.raise_()
        self._settings_dialog.activateWindow()

    def _on_settings_changed(self, settings: dict):
        """设置变更回调"""
        # TODO: 应用设置到运行时
        self._tray.show_message("设置", "设置已保存")

    def _create_capture_widget(self) -> CapturePreviewWidget:
        """创建截图预览组件"""
        if self._capture_widget is None:
            self._capture_widget = CapturePreviewWidget()
        return self._capture_widget

    def _on_main_window_closed(self):
        """主窗口关闭 → 最小化到托盘"""
        self._tray.show_message(
            "原神狗粮清扫器", "已在后台运行，双击托盘图标可重新打开窗口"
        )