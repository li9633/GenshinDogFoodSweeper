"""
系统托盘管理器
==============
负责系统托盘图标、右键菜单、状态切换。
"""

from __future__ import annotations

from PySide6.QtCore import QObject
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon


class TrayManager(QObject):
    """系统托盘管理器

    用法：
        _tray = TrayManager(app=app, engine=engine)
    """

    def __init__(
        self,
        app,
        engine,
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self._app = app
        self._engine = engine

        self._tray = QSystemTrayIcon(parent=None)
        self._tray.setToolTip("原神狗粮清扫器")

        self._set_icon()
        self._build_menu()

        # 退出时清理
        app.aboutToQuit.connect(self.cleanup)

        self._tray.show()

    # ---------- 公开方法 ----------

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
            # 生成一个程序化图标作为兜底
            self._tray.setIcon(self._generate_fallback_icon())

    def _build_menu(self):
        self._menu = QMenu()

        self._action_show = QAction("显示窗口")
        self._action_show.triggered.connect(self._show_main_window)
        self._menu.addAction(self._action_show)

        self._menu.addSeparator()

        self._action_exit = QAction("退出程序")
        self._action_exit.triggered.connect(self._quit_app)
        self._menu.addAction(self._action_exit)

        self._tray.setContextMenu(self._menu)

    def _show_main_window(self):
        """恢复并置顶主窗口"""
        for obj in self._engine.rootObjects():
            if hasattr(obj, 'show'):
                obj.show()
                obj.raise_()
                obj.requestActivate()

    def _quit_app(self):
        """优雅退出：关闭窗口 → 等 QML 解绑 → 退出"""
        from PySide6.QtCore import QTimer

        for obj in self._engine.rootObjects():
            if hasattr(obj, 'close'):
                obj.close()
        # 延迟到下一轮事件循环，确保 QML 先完成解绑
        QTimer.singleShot(0, self._app.quit)

    @staticmethod
    def _find_icon() -> str | None:
        """查找应用图标（兼容开发模式和打包后）"""
        import sys
        from pathlib import Path

        if getattr(sys, 'frozen', False):
            base = Path(sys.executable).parent
        else:
            base = Path(__file__).parent.parent.parent

        candidates = [
            base / "resources" / "app.ico",
            base / "resources" / "app.png",
            base / "resources" / "icons" / "app.ico",
        ]
        for p in candidates:
            if p.exists():
                return str(p)
        return None

    @staticmethod
    def _generate_fallback_icon():
        """用 QPainter 绘制一个紫色圆形图标作为兜底"""
        from PySide6.QtCore import QSize, Qt
        from PySide6.QtGui import QIcon, QPainter, QPixmap

        size = QSize(32, 32)
        pixmap = QPixmap(size)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(Qt.GlobalColor.magenta)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(2, 2, 28, 28)
        painter.end()

        return QIcon(pixmap)