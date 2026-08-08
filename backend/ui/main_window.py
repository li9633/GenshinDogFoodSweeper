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
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        # --- 标题栏 ---
        header = QHBoxLayout()
        title = QLabel("原神狗粮清扫器")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()

        self._label_server = QLabel("服务: 启动中...")
        header.addWidget(self._label_server)
        header.addSpacing(8)

        self._btn_scan = QPushButton("开始扫描")
        self._btn_scan.clicked.connect(self.scan_requested.emit)
        header.addWidget(self._btn_scan)

        self._btn_stop = QPushButton("停止")
        self._btn_stop.setEnabled(False)
        self._btn_stop.clicked.connect(self.stop_requested.emit)
        header.addWidget(self._btn_stop)

        root.addLayout(header)

        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #3a3a3a;")
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
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e1e;
            }
            QPushButton {
                padding: 6px 16px;
                border: 1px solid #4a4a4a;
                border-radius: 3px;
                background-color: #2d2d2d;
                color: #e0e0e0;
            }
            QPushButton:hover {
                background-color: #3d3d3d;
            }
            QPushButton:disabled {
                color: #666;
            }
            QLabel {
                color: #e0e0e0;
            }
            QStatusBar {
                background-color: #252525;
                color: #888;
                border-top: 1px solid #3a3a3a;
            }
        """)