"""
主窗口
======
包含截图预览、扫描控制、状态栏。
关闭窗口时最小化到托盘，不退出程序。
"""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)


class MainWindow(QMainWindow):
    """主窗口"""

    scan_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    closed = pyqtSignal()  # 窗口关闭 → 最小化到托盘

    _is_dark = True  # 当前主题状态

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("原神狗粮清扫器")
        self.setMinimumSize(800, 600)

        self._build_ui()
        self._apply_styles()

    # ---------- 公开方法 ----------

    def set_scanning(self, active: bool):
        self._btn_scan.setEnabled(not active)
        self._btn_stop.setEnabled(active)
        self._status_label.setText("扫描中…" if active else "就绪")

    def set_server_status(self, running: bool, port: int = 0):
        text = f"服务: 运行中 (:{port})" if running else "服务: 未启动"
        self._label_server.setText(text)

    def set_capture_preview(self, widget: QWidget):
        """将截图预览组件嵌入主窗口"""
        self._preview_container.layout().addWidget(widget)

    # ---------- 事件 ----------

    def closeEvent(self, event):
        """关闭窗口 → 隐藏到托盘，不退出"""
        event.ignore()
        self.hide()
        self.closed.emit()

    # ---------- UI 构建 ----------

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # --- 标题栏 ---
        header = QHBoxLayout()
        title = QLabel("原神狗粮清扫器")
        title.setProperty("class", "title")
        header.addWidget(title)
        header.addStretch()

        self._label_server = QLabel("服务: 启动中...")
        self._label_server.setProperty("class", "hint")
        header.addWidget(self._label_server)
        header.addSpacing(12)

        self._btn_theme = QPushButton("☀️")
        self._btn_theme.setProperty("class", "icon-btn")
        self._btn_theme.setToolTip("切换主题")
        self._btn_theme.clicked.connect(self.toggle_theme)
        header.addWidget(self._btn_theme)

        self._btn_scan = QPushButton("开始扫描")
        self._btn_scan.setProperty("class", "primary")
        self._btn_scan.clicked.connect(self.scan_requested.emit)
        header.addWidget(self._btn_scan)

        self._btn_stop = QPushButton("停止")
        self._btn_stop.setProperty("class", "danger")
        self._btn_stop.setEnabled(False)
        self._btn_stop.clicked.connect(self.stop_requested.emit)
        header.addWidget(self._btn_stop)

        root.addLayout(header)

        # 分隔线
        line = QFrame()
        line.setProperty("class", "separator")
        root.addWidget(line)

        # --- 预览区域 ---
        self._preview_container = QFrame()
        self._preview_container.setLayout(QVBoxLayout())
        self._preview_container.layout().setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._preview_container, stretch=1)

        # --- 状态栏 ---
        self._status_bar = QStatusBar()
        self._status_label = QLabel("就绪")
        self._status_bar.addWidget(self._status_label)
        self.setStatusBar(self._status_bar)

    def _apply_styles(self):
        self._load_stylesheet("style.qss")

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
        """切换明暗主题"""
        self._is_dark = not self._is_dark
        if self._is_dark:
            self._load_stylesheet("style.qss")
            self._btn_theme.setText("☀️")
        else:
            self._load_stylesheet("style-light.qss")
            self._btn_theme.setText("🌙")