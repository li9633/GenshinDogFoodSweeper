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

import webbrowser
from collections.abc import Callable
from dataclasses import dataclass

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from utils.env_manager import EnvManager
from utils.log_bridge import set_status_callback

from backend.api.launcher import ApiLauncher

from .managers.status_bar_manager import StatusBarManager
from .managers.theme_manager import ThemeManager
from .pages.cleaner_page import CleanerPage
from .pages.debug_page import DebugPage
from .pages.rules_page import RulesPage
from .pages.settings_page import SettingsPage
from .tray import TrayManager
from .widgets.capture_view import CapturePreviewWidget


@dataclass(frozen=True)
class PageEntry:
    """页面注册项 — 单一数据源，同时驱动导航按钮和页面懒加载"""

    key: str
    label: str
    factory: Callable[[], QWidget]


class MainWindow(QMainWindow):
    """主窗口 — 应用协调器"""

    app_exit_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        title = "原神狗粮清扫器"
        if EnvManager.is_debug():
            title += "（调试模式）"
        self.setWindowTitle(title)
        self.setMinimumSize(1200, 800)

        self._theme = ThemeManager()
        self._theme.apply()

        self._scanning = False
        self._backend = ApiLauncher(self._on_server_status)

        self._capture_widget = CapturePreviewWidget()

        self._nav_buttons: dict[str, QPushButton] = {}
        self._page_factories: dict[str, Callable[[], QWidget]] = {}
        self._pages: dict[str, QWidget] = {}
        self._stack: QStackedWidget | None = None

        self._build_shell()

        QTimer.singleShot(0, lambda: self._switch_page("cleaner"))

        set_status_callback(
            lambda level, msg, dur: self._status_bar.show(msg, dur, level)
        )

        self._tray = TrayManager()
        self._connect_tray()

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
        self._status_bar.show(message, duration, level)

    def set_scanning(self, active: bool):
        self.show_status("扫描中…" if active else "就绪")

    def _on_server_status(self, running: bool, port: int = 0):
        text = f"服务: 运行中 (:{port})" if running else "服务: 未启动"
        self._label_server.setText(text)
        if running:
            self.show_status(f"后端服务已启动 → http://127.0.0.1:{port}", 3000)

    def start_backend(self) -> None:
        """启动后端 API 服务"""
        self._backend.start()

    def shutdown(self):
        self._backend.stop()

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
            pages.append(PageEntry("debug", "调试", lambda: DebugPage(self._capture_widget)))
        return pages

    def _create_cleaner_page(self) -> CleanerPage:
        """创建清理器页面并连接扫描信号"""
        page = CleanerPage()
        page.scan_requested.connect(self._on_start_scan)
        page.stop_requested.connect(self._on_stop_scan)
        return page

    def _create_settings_page(self) -> SettingsPage:
        page = SettingsPage()
        page.theme_changed.connect(self._theme.apply)
        page.sync_started.connect(lambda: self.show_status("正在同步圣遗物数据…", 0))
        page.sync_progress.connect(
            lambda c, t, n: self.show_status(f"正在同步: {c}/{t}  {n}", 0)
        )
        page.sync_finished.connect(lambda: self.show_status("同步完成", 3000))
        return page

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
        webbrowser.open(ApiLauncher.PANEL_URL)
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

        self._status_bar = StatusBarManager(self)

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

    def toggle_theme(self):
        self._theme.toggle()