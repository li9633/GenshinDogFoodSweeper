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
from dataclasses import dataclass, field

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from utils.env_manager import EnvManager
from utils.log_bridge import set_status_callback

from backend.api.launcher import ApiLauncher

from .managers.page_navigator import PageNavigator
from .managers.status_bar_manager import StatusBarManager
from .managers.theme_manager import ThemeManager
from .pages.debug_page import DebugPage
from .pages.dogfood_page import DogfoodPage
from .pages.locker_page import LockerPage
from .pages.rules_page import RulesPage
from .pages.scanner_page import ScannerPage
from .pages.settings_page import SettingsPage
from .tray import TrayManager
from .widgets.capture_view import CapturePreviewWidget
from .widgets.sidebar import NavItem, Sidebar


@dataclass
class MenuItem:
    """菜单项 — 单一数据源，同时驱动 Sidebar（层级）和 PageNavigator（扁平）

    factory 为 None → 父节点（仅展开/折叠）；非 None → 叶子节点（点击切换页面）。
    """

    key: str
    label: str
    children: list[MenuItem] = field(default_factory=list)
    factory: Callable[[], QWidget] | None = None


class MainWindow(QMainWindow):
    """主窗口 — 应用协调器"""

    app_exit_requested = Signal()

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

        self._navigator: PageNavigator | None = None
        self._sidebar: Sidebar | None = None

        self._build_shell()

        QTimer.singleShot(0, lambda: self._navigator.switch_to("dogfood"))

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

        # 后台线程预热 OCR 引擎，避免首次识别时 UI 卡住
        QTimer.singleShot(2000, self._start_ocr_worker)

    def _start_ocr_worker(self) -> None:
        from backend.automation.ocr_worker import OcrWorker

        self._status_bar.show("OCR 引擎预热中…", 0, "INFO")
        QApplication.processEvents()

        worker = OcrWorker.instance()
        worker.ready.connect(
            lambda: self._status_bar.show("OCR 引擎就绪", 3000, "INFO")
        )
        worker.task_error.connect(
            lambda msg, _: (
                self._status_bar.show(f"OCR 错误: {msg}", 5000, "ERROR")
                if msg and "模型未下载" not in msg
                else None
            )
        )

    # ---------- 公开 API ----------

    def get_page(self, key: str) -> QWidget | None:
        """获取已加载的页面实例（未加载返回 None）"""
        if self._navigator is None:
            return None
        return self._navigator.get_page(key)

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
        from backend.automation.ocr_worker import OcrWorker
        OcrWorker.destroy_instance()
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

    def _page_registry(self) -> list[MenuItem]:
        """菜单注册表 — 唯一数据源，同时驱动 Sidebar 层级和 PageNavigator 注册"""
        items = [
            MenuItem("launcher", "启动", children=[
                MenuItem("dogfood", "狗粮清理器", factory=lambda: DogfoodPage()),
                MenuItem("scanner", "圣遗物扫描器", factory=lambda: ScannerPage()),
                MenuItem("locker", "圣遗物锁定器", factory=lambda: LockerPage()),
            ]),
            MenuItem("rules", "规则预设", factory=lambda: RulesPage()),
            MenuItem("settings", "设置", factory=lambda: SettingsPage(
                on_theme_changed=self._theme.apply,
                on_status=self.show_status,
            )),
        ]
        if EnvManager.is_debug():
            items.append(MenuItem("debug", "调试", factory=lambda: DebugPage(self._capture_widget)))
        return items

    # ---------- 设置 & 面板 ----------

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
        self._tray.show_message("扫描", "已开始扫描圣遗物…")

    def _on_stop_scan(self):
        # TODO: 调用 API POST /api/scan/stop
        self._scanning = False
        self._tray.set_scanning(False)
        self.set_scanning(False)
        self._tray.show_message("扫描", "扫描已停止")

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
        items = self._page_registry()

        # 转换为 NavItem 层级给 Sidebar
        def _to_nav_items(menu_items: list[MenuItem]) -> list[NavItem]:
            return [
                NavItem(key=item.key, label=item.label, children=_to_nav_items(item.children))
                for item in menu_items
            ]
        self._sidebar = Sidebar(_to_nav_items(items))
        root.addWidget(self._sidebar)

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

        self._navigator = PageNavigator(self._stack, self._sidebar)

        # 注册所有叶子页面到 PageNavigator
        def _register_recursive(menu_items: list[MenuItem]) -> None:
            for item in menu_items:
                if item.factory is not None:
                    self._navigator.register(item.key, item.factory)
                _register_recursive(item.children)
        _register_recursive(items)
        self._sidebar.page_selected.connect(self._navigator.switch_to)

        self._status_bar = StatusBarManager(self)

    # ---------- 导航 / 懒加载 ----------

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
        if self._navigator is not None:
            self._navigator.switch_to(key)

    def toggle_theme(self):
        self._theme.toggle()