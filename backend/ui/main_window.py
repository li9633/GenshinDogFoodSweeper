"""
主窗口（应用协调器）
====================
职责：
  1. Shell 布局（侧边栏 + QStackedWidget + 状态栏）
  2. 页面注册与懒加载
  3. 托盘管理
  4. 后端服务生命周期
  5. 扫描控制
  6. 设置对话框
关闭窗口时最小化到托盘，不退出程序。
"""

from __future__ import annotations

import threading
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)
from utils.env_manager import EnvManager
from utils.log_bridge import set_status_callback
from utils.settings_manager import settings

from .pages.cleaner_page import CleanerPage
from .pages.debug_page import DebugPage
from .pages.rules_page import RulesPage
from .pages.settings_page import SettingsPage
from .tray import TrayManager
from .widgets.capture_view import CapturePreviewWidget

# 日志级别 → 状态栏文字颜色，对齐 loguru 默认配色
_LEVEL_COLORS: dict[str, str] = {
    "DEBUG": "#3498DB",  # 蓝 — loguru debug = cyan
    "INFO": "#B8B5C0",  # 灰 — loguru info = default
    "SUCCESS": "#27AE60",  # 绿 — loguru success = green
    "WARNING": "#F39C12",  # 橙 — loguru warning = yellow
    "ERROR": "#E74C3C",  # 红 — loguru error = red
    "CRITICAL": "#C0392B",  # 深红 — loguru critical = red on white
}


@dataclass(frozen=True)
class PageEntry:
    """页面注册项 — 单一数据源，同时驱动导航按钮和页面懒加载"""

    key: str
    label: str
    factory: Callable[[], QWidget]


class MainWindow(QMainWindow):
    """主窗口 — 应用协调器"""

    # 供外部（main.py）监听的信号
    app_exit_requested = pyqtSignal()

    # 状态栏更新信号（跨线程安全）: (level, message, duration)
    _status_signal = pyqtSignal(str, str, int)

    PANEL_URL = "http://127.0.0.1:8765"
    SERVER_PORT = 8765

    def __init__(self, parent=None):
        super().__init__(parent)

        title = "原神狗粮清扫器"
        if EnvManager.is_debug():
            title += "（调试模式）"
        self.setWindowTitle(title)
        self.setMinimumSize(1200, 800)

        self._is_dark = settings.get_theme() == "dark"

        self._scanning = False
        self._server_thread: threading.Thread | None = None

        self._capture_widget = CapturePreviewWidget()

        self._nav_buttons: dict[str, QPushButton] = {}
        self._page_factories: dict[str, Callable[[], QWidget]] = {}
        self._pages: dict[str, QWidget] = {}
        self._stack: QStackedWidget | None = None

        # QSS 提前到 build_shell / switch_page 之前加载，
        # 让样式在 widget 创建时即解析完毕，避免 addWidget 时集中解析
        self._apply_styles()

        self._build_shell()

        QTimer.singleShot(0, lambda: self._switch_page("cleaner"))

        # 注册日志 → 状态栏的回调
        set_status_callback(lambda level, msg, dur: self.show_status(msg, dur, level))

        # 连接状态栏信号（保证跨线程安全）
        self._status_signal.connect(self._do_show_status)

        # 托盘
        self._tray = TrayManager()
        self._connect_tray()

        # 托盘提示
        QTimer.singleShot(
            500,
            lambda: self._tray.show_message(
                "原神狗粮清扫器", "已在后台运行，右键托盘图标操作"
            ),
        )

    # ---------- 公开 API ----------

    def register_page(self, key: str, factory: Callable[[], QWidget]):
        """注册页面工厂函数（首次访问时懒加载）"""
        self._page_factories[key] = factory

    def get_page(self, key: str) -> QWidget | None:
        """获取已加载的页面实例（未加载返回 None）"""
        return self._pages.get(key)

    def show_status(self, message: str, duration: int = 0, level: str = "INFO"):
        """线程安全：通过信号调度到主线程执行 QStatusBar.showMessage"""
        self._status_signal.emit(level, message, duration)

    def _do_show_status(self, level: str, message: str, duration: int):
        """实际执行 showMessage（保证在主线程），根据日志级别渲染颜色

        - 文字颜色：QPalette.WindowText（不受 QSS 覆盖）
        - CRITICAL 背景：setStyleSheet（QPalette.Window 会被 QSS 覆盖，
          必须用样式表才能覆盖全局 QSS 的 background-color）
        """
        palette = self.statusBar().palette()
        if level.upper() == "CRITICAL":
            self.statusBar().setStyleSheet("QStatusBar { background-color: #C0392B; }")
            palette.setColor(QPalette.ColorRole.WindowText, QColor("#FFFFFF"))
        else:
            self.statusBar().setStyleSheet("")
            color = _LEVEL_COLORS.get(level.upper(), "#000000")
            palette.setColor(QPalette.ColorRole.WindowText, QColor(color))
        self.statusBar().setPalette(palette)
        self.statusBar().showMessage(message, duration)

    def set_scanning(self, active: bool):
        self.show_status("扫描中…" if active else "就绪")

    def set_server_status(self, running: bool, port: int = 0):
        text = f"服务: 运行中 (:{port})" if running else "服务: 未启动"
        self._label_server.setText(text)
        if running:
            self.show_status(f"后端服务已启动 → http://127.0.0.1:{port}", 3000)

    def shutdown(self):
        """清理资源"""
        self._stop_backend()

    # ---------- 事件 ----------

    def closeEvent(self, event):
        """关闭窗口 → 隐藏到托盘，不退出"""
        event.ignore()
        self.hide()
        self._tray.show_message(
            "原神狗粮清扫器", "已在后台运行，双击托盘图标可重新打开窗口"
        )

    # ---------- 页面注册表 ----------

    def _page_registry(self) -> list[PageEntry]:
        """页面注册表 — 单一数据源，同时驱动导航栏和懒加载"""
        pages = [
            PageEntry("cleaner", "清理器", self._create_cleaner_page),
            PageEntry("rules", "规则预设", lambda: RulesPage()),
            PageEntry("settings", "设置", self._create_settings_page),
        ]
        if EnvManager.is_debug():
            pages.append(PageEntry("debug", "调试", self._create_debug_page))
        return pages

    def _create_cleaner_page(self) -> CleanerPage:
        """创建清理器页面并连接扫描信号"""
        page = CleanerPage()
        page.scan_requested.connect(self._on_start_scan)
        page.stop_requested.connect(self._on_stop_scan)
        return page

    def _create_debug_page(self) -> DebugPage:
        """创建调试页面并注册所有子面板"""
        from .pages.debug_panels.element_detection_panel import ElementDetectionPanel
        from .pages.debug_panels.region_marker_panel import RegionMarkerPanel
        from .pages.debug_panels.status_bar_test_panel import StatusBarTestPanel

        page = DebugPage()
        page.add_tab(RegionMarkerPanel(self._capture_widget), "区域标记", show_preview=True)
        page.add_tab(ElementDetectionPanel(self._capture_widget), "元素定位", show_preview=True)
        page.add_tab(StatusBarTestPanel(), "状态栏")
        page.set_preview(self._capture_widget)
        return page

    def _create_settings_page(self) -> SettingsPage:
        """创建设置页面并连接主题变更 + 同步锁定信号"""
        page = SettingsPage()
        page.theme_changed.connect(self.apply_theme)
        page.sync_started.connect(lambda: self.show_status("正在同步圣遗物数据…", 0))
        page.sync_progress.connect(
            lambda c, t, n: self.show_status(f"正在同步: {c}/{t}  {n}", 0)
        )
        page.sync_finished.connect(lambda: self.show_status("同步完成", 3000))
        return page

    # ---------- 主题 ----------

    def apply_theme(self, theme: str):
        """应用指定主题"""
        self._is_dark = theme == "dark"
        self._apply_styles()

    # ---------- 托盘 ----------

    def _connect_tray(self):
        self._tray.scan_requested.connect(self._on_start_scan)
        self._tray.stop_requested.connect(self._on_stop_scan)
        self._tray.panel_requested.connect(self._open_browser)
        self._tray.settings_requested.connect(self._open_settings)
        self._tray.exit_requested.connect(self._on_exit)

    def _on_exit(self):
        self._tray.cleanup()
        self.shutdown()
        self.app_exit_requested.emit()

    # ---------- 后端服务 ----------

    def _start_backend(self):
        def run_server():
            import uvicorn

            try:
                uvicorn.run(
                    "backend.server:app",
                    host="127.0.0.1",
                    port=self.SERVER_PORT,
                    log_config=None,
                )
            except (OSError, SystemExit) as e:
                from utils.logger import log

                log.error(f"服务器启动失败: {e}")

        self._server_thread = threading.Thread(target=run_server, daemon=True)
        self._server_thread.start()
        self.set_server_status(True, self.SERVER_PORT)

        from utils.logger import log

        log.info(f"后端服务已启动 → {self.PANEL_URL}")

    def _stop_backend(self):
        pass  # daemon 线程随进程退出

    # ---------- 扫描控制 ----------

    def _on_start_scan(self):
        # TODO: 调用 API POST /api/scan/start
        self._scanning = True
        self._tray.set_scanning(True)
        self.set_scanning(True)
        self._update_cleaner_buttons(True)
        self._tray.show_message("扫描", "已开始扫描圣遗物…")

    def _on_stop_scan(self):
        # TODO: 调用 API POST /api/scan/stop
        self._scanning = False
        self._tray.set_scanning(False)
        self.set_scanning(False)
        self._update_cleaner_buttons(False)
        self._tray.show_message("扫描", "扫描已停止")

    def _update_cleaner_buttons(self, active: bool):
        page = self.get_page("cleaner")
        if page is not None:
            page.set_scanning(active)

    # ---------- 设置 & 面板 ----------

    def _open_browser(self):
        """打开 Web 管理面板"""
        webbrowser.open(self.PANEL_URL)
        self.show_status("已打开 Web 管理面板", 3000)

    def _open_settings(self):
        """打开设置 → 切换到侧边栏设置页面"""
        self.show()
        self.raise_()
        self.activateWindow()
        self._switch_page("settings")
        self.show_status("设置页面", 2000)

    # ---------- Shell 构建 ----------

    def _build_shell(self):
        """构建窗口骨架：侧边栏 + 内容区 + 状态栏"""
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # --- 左侧导航栏 ---
        nav = self._build_nav()
        root.addWidget(nav)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.VLine)
        line.setProperty("class", "separator")
        root.addWidget(line)

        # --- 右侧内容区 ---
        content = QVBoxLayout()
        content.setContentsMargins(16, 16, 16, 16)

        content.addLayout(self._build_toolbar())

        line2 = QFrame()
        line2.setProperty("class", "separator")
        content.addWidget(line2)

        self._stack = QStackedWidget()
        placeholder = QLabel("加载中…")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setProperty("class", "hint")
        self._stack.addWidget(placeholder)
        content.addWidget(self._stack, stretch=1)

        root.addLayout(content, stretch=1)

        # --- 状态栏 ---
        QTimer.singleShot(0, self._init_status_bar)

    def _init_status_bar(self):
        """延迟初始化状态栏（避免构造期间阻塞）"""
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("就绪")

    def _build_nav(self) -> QWidget:
        """
        构建左侧导航栏（el-menu 风格）
        - 深色侧边栏背景，与内容区形成对比
        - 菜单项无边框、无圆角、左对齐
        - 激活项左侧金色指示条 + 背景高亮
        """
        nav = QWidget()
        nav.setFixedWidth(160)
        nav.setProperty("class", "nav")
        layout = QVBoxLayout(nav)
        layout.setContentsMargins(0, 12, 0, 12)
        layout.setSpacing(0)

        for entry in self._page_registry():
            btn = QPushButton(f"  {entry.label}")
            btn.setProperty("class", "nav-btn")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, k=entry.key: self._switch_page(k))
            self._nav_buttons[entry.key] = btn
            self.register_page(entry.key, entry.factory)
            layout.addWidget(btn)

        layout.addStretch()
        return nav

    def _build_toolbar(self) -> QHBoxLayout:
        """构建顶部工具栏（全局）"""
        toolbar = QHBoxLayout()

        self._label_server = QLabel("服务: 启动中...")
        self._label_server.setProperty("class", "hint")
        toolbar.addWidget(self._label_server)
        toolbar.addStretch()

        return toolbar

    # ---------- 导航 / 懒加载 ----------

    def _switch_page(self, key: str):
        """
        切换页面，首次访问时懒加载。

        流程:
          1. 检查 _pages 缓存
          2. 未命中则调用工厂函数创建
          3. 添加到 QStackedWidget（临时隐藏避免布局重算）
          4. 切换显示
        """
        if key not in self._pages:
            factory = self._page_factories.get(key)
            if factory is None:
                return
            page = factory()
            self._pages[key] = page

            self._stack.setUpdatesEnabled(False)
            self._stack.addWidget(page)
            self._stack.setUpdatesEnabled(True)

        self._stack.setCurrentWidget(self._pages[key])

        app_style = QApplication.style()
        for k, btn in self._nav_buttons.items():
            btn.setProperty("active", k == key)
            app_style.unpolish(btn)
            app_style.polish(btn)

    def _apply_styles(self):
        filename = "style.qss" if self._is_dark else "style-light.qss"
        self._load_stylesheet(filename)

    @staticmethod
    def _load_stylesheet(filename: str):
        from pathlib import Path

        from PyQt6.QtWidgets import QApplication

        qss_path = Path(__file__).parent / "resources" / filename
        if qss_path.exists():
            with open(qss_path, "r", encoding="utf-8") as f:
                qss = f.read()
            QApplication.instance().setStyleSheet(qss)

    def toggle_theme(self):
        """切换明暗主题并持久化"""
        self._is_dark = not self._is_dark
        theme = "dark" if self._is_dark else "light"
        settings.set_theme(theme)
        self._apply_styles()