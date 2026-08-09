"""
系统托盘管理器
==============
负责系统托盘图标、右键菜单、状态切换。
"""

from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon


class TrayManager(QObject):
    """系统托盘管理器"""

    # 信号：通知外部（App 层）用户操作
    scan_requested = pyqtSignal()  # 开始扫描
    stop_requested = pyqtSignal()  # 停止扫描
    panel_requested = pyqtSignal()  # 打开 Web 面板
    settings_requested = pyqtSignal()  # 打开设置
    exit_requested = pyqtSignal()  # 退出程序

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._tray = QSystemTrayIcon(parent=None)
        self._tray.setToolTip("原神狗粮清扫器")

        # 图标
        self._set_icon()

        # 菜单
        self._build_menu()

        self._tray.show()

    # ---------- 公开方法 ----------

    def set_scanning(self, active: bool):
        """更新扫描状态（切换菜单项文字）"""
        self._action_scan.setEnabled(not active)
        self._action_stop.setEnabled(active)
        if active:
            self._tray.setToolTip("原神狗粮清扫器 — 扫描中…")
        else:
            self._tray.setToolTip("原神狗粮清扫器")

    def show_message(self, title: str, message: str, duration_ms: int = 3000):
        """弹出气泡提示"""
        self._tray.showMessage(
            title, message, QSystemTrayIcon.MessageIcon.Information, duration_ms
        )

    def cleanup(self):
        """
        显式隐藏并销毁托盘图标。
        应在 QApplication.aboutToQuit 信号中连接此方法。
        """
        self._tray.hide()
        self._tray.deleteLater()

    # ---------- 内部 ----------

    def _set_icon(self):
        """设置托盘图标"""
        icon_path = self._find_icon()
        if icon_path:
            self._tray.setIcon(QIcon(icon_path))
        else:
            # 使用 Qt 内置图标作为兜底
            from PyQt6.QtWidgets import QApplication

            self._tray.setIcon(
                QApplication.style().standardIcon(
                    QApplication.style().StandardPixmap.SP_ComputerIcon
                )
            )

    def _build_menu(self):
        menu = QMenu()

        self._action_scan = QAction("开始扫描")
        self._action_scan.triggered.connect(self.scan_requested.emit)
        menu.addAction(self._action_scan)

        self._action_stop = QAction("停止扫描")
        self._action_stop.setEnabled(False)
        self._action_stop.triggered.connect(self.stop_requested.emit)
        menu.addAction(self._action_stop)

        menu.addSeparator()

        action_panel = QAction("🌐 打开管理面板")
        action_panel.triggered.connect(self.panel_requested.emit)
        menu.addAction(action_panel)

        action_settings = QAction("⚙ 设置")
        action_settings.triggered.connect(self.settings_requested.emit)
        menu.addAction(action_settings)

        menu.addSeparator()

        action_exit = QAction("X 退出")
        action_exit.triggered.connect(self.exit_requested.emit)
        menu.addAction(action_exit)

        self._tray.setContextMenu(menu)

    @staticmethod
    def _find_icon() -> str | None:
        """查找应用图标"""
        from pathlib import Path

        candidates = [
            Path(__file__).parent.parent.parent / "resources" / "app.ico",
            Path(__file__).parent.parent.parent / "resources" / "icons" / "app.ico",
        ]
        for p in candidates:
            if p.exists():
                return str(p)
        return None
