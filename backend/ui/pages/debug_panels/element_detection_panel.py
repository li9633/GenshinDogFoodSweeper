"""元素定位检测面板 — View 层（仅 UI 渲染 + 简单交互）"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from utils.logger import log

from backend.ui.presenters.async_runner import run_async
from backend.ui.presenters.element_detection_presenter import (
    ElementDetectionPresenter,
)


class ElementDetectionPanel(QWidget):
    """元素定位检测 — View 层"""

    def __init__(self, capture_widget: QWidget | None = None, parent=None):
        super().__init__(parent)
        self._capture_widget = capture_widget
        self._presenter = ElementDetectionPresenter()
        self._last_matches: list[tuple[str, int, int, int, int]] = []
        self._build_ui()
        self._refresh_template_list()

    # ---------- UI ----------

    def _build_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        content = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        content.setLayout(layout)

        # 添加检测条件
        add_group = QGroupBox("添加检测条件")
        add_layout = QVBoxLayout()
        add_layout.setContentsMargins(4, 4, 4, 4)
        add_layout.setSpacing(3)
        add_group.setLayout(add_layout)

        row1 = QHBoxLayout()
        row1.setSpacing(3)
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("搜索模板…")
        self._search_input.textChanged.connect(self._on_search_changed)
        row1.addWidget(self._search_input)
        self._btn_refresh = QPushButton("⟳")
        self._btn_refresh.setFixedWidth(30)
        self._btn_refresh.setToolTip("刷新模板列表")
        self._btn_refresh.clicked.connect(self._on_refresh)
        row1.addWidget(self._btn_refresh)
        add_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(3)
        row2.addWidget(QLabel("模板:"))
        self._combo_template = QComboBox()
        self._combo_template.setMinimumWidth(120)
        self._combo_template.currentIndexChanged.connect(self._on_template_changed)
        row2.addWidget(self._combo_template, stretch=1)
        row2.addWidget(QLabel("阈值:"))
        self._spin_threshold = QDoubleSpinBox()
        self._spin_threshold.setRange(0.0, 1.0)
        self._spin_threshold.setSingleStep(0.05)
        self._spin_threshold.setValue(0.80)
        self._spin_threshold.setDecimals(2)
        self._spin_threshold.setMinimumWidth(55)
        row2.addWidget(self._spin_threshold)
        self._btn_add = QPushButton("+ 添加")
        self._btn_add.clicked.connect(self._on_add_condition)
        row2.addWidget(self._btn_add)
        add_layout.addLayout(row2)

        # 预览 + 区域
        preview_region_row = QHBoxLayout()
        preview_region_row.setSpacing(4)
        self._preview_label = QLabel()
        self._preview_label.setFixedSize(100, 80)
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setStyleSheet(
            "QLabel { border: 1px solid #555; background: #2b2b2b; color: #888; }"
        )
        self._preview_label.setText("无预览")
        preview_region_row.addWidget(self._preview_label)

        region_col = QVBoxLayout()
        region_col.setSpacing(2)
        region_spin_row = QHBoxLayout()
        region_spin_row.setSpacing(2)
        self._chk_region = QCheckBox("限定区域")
        region_spin_row.addWidget(self._chk_region)
        for label_text, attr in [
            ("X:", "_spin_rx"),
            ("Y:", "_spin_ry"),
            ("W:", "_spin_rw"),
            ("H:", "_spin_rh"),
        ]:
            region_spin_row.addWidget(QLabel(label_text))
            spin = QSpinBox()
            spin.setRange(0, 9999)
            spin.setMinimumWidth(50)
            setattr(self, attr, spin)
            region_spin_row.addWidget(spin)
        self._spin_rw.setValue(200)
        self._spin_rh.setValue(100)
        region_spin_row.addStretch()
        region_col.addLayout(region_spin_row)

        region_btn_row = QHBoxLayout()
        region_btn_row.setSpacing(3)
        self._btn_paste = QPushButton("粘贴")
        self._btn_paste.clicked.connect(self._on_paste_region)
        region_btn_row.addWidget(self._btn_paste)
        region_btn_row.addStretch()
        region_col.addLayout(region_btn_row)
        preview_region_row.addLayout(region_col, stretch=1)
        add_layout.addLayout(preview_region_row)
        layout.addWidget(add_group)

        # 条件列表
        list_group = QGroupBox("检测条件列表（全部匹配才算通过）")
        list_layout = QVBoxLayout()
        list_layout.setContentsMargins(4, 4, 4, 4)
        list_layout.setSpacing(3)
        list_group.setLayout(list_layout)

        self._condition_list = QListWidget()
        self._condition_list.setMaximumHeight(100)
        self._condition_list.currentItemChanged.connect(self._on_condition_selected)
        list_layout.addWidget(self._condition_list)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(3)
        self._btn_remove = QPushButton("移除选中")
        self._btn_remove.clicked.connect(self._on_remove_condition)
        btn_row.addWidget(self._btn_remove)
        self._btn_clear = QPushButton("清空列表")
        self._btn_clear.clicked.connect(self._on_clear_conditions)
        btn_row.addWidget(self._btn_clear)
        btn_row.addStretch()
        list_layout.addLayout(btn_row)
        layout.addWidget(list_group)

        self._btn_detect = QPushButton("检测定位")
        self._btn_detect.setProperty("class", "primary")
        self._btn_detect.clicked.connect(self._on_detect)
        layout.addWidget(self._btn_detect)

        reg_row = QHBoxLayout()
        reg_row.setSpacing(3)
        self._edit_display_name = QLineEdit()
        self._edit_display_name.setPlaceholderText("注册名称（留空用文件名）")
        reg_row.addWidget(self._edit_display_name)
        self._btn_register = QPushButton("注册区域")
        self._btn_register.clicked.connect(self._on_register_region)
        reg_row.addWidget(self._btn_register)
        layout.addLayout(reg_row)

        scroll.setWidget(content)
        outer_layout.addWidget(scroll)

    # ---------- 模板列表 ----------

    def _refresh_template_list(self, keyword: str = "") -> None:
        self._combo_template.clear()
        templates = self._presenter.list_templates(keyword)
        for key, filename in templates.items():
            self._combo_template.addItem(f"{key} ({filename})", key)

    def _on_refresh(self) -> None:
        self._presenter.reload_templates()
        self._refresh_template_list()

    def _on_search_changed(self, text: str) -> None:
        self._refresh_template_list(text.strip())

    def _on_template_changed(self, _idx: int) -> None:
        key = self._combo_template.currentData()
        if not key:
            self._update_preview(None)
            return
        region = self._presenter.get_template_region(key)
        if region:
            self._spin_rx.setValue(region[0])
            self._spin_ry.setValue(region[1])
            self._spin_rw.setValue(region[2])
            self._spin_rh.setValue(region[3])
            self._chk_region.setChecked(True)
        else:
            self._chk_region.setChecked(False)
        self._update_preview(key)

    def _update_preview(self, key: str | None) -> None:
        if key is None:
            self._preview_label.setText("无预览")
            return
        path = self._presenter.get_template_path(key)
        if path is None:
            self._preview_label.setText("无文件")
            return
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            self._preview_label.setText("加载失败")
            return
        pw, ph = self._preview_label.width(), self._preview_label.height()
        scaled = pixmap.scaled(
            pw - 6,
            ph - 6,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._preview_label.setPixmap(scaled)

    # ---------- 条件管理 ----------

    def _get_existing_conditions(self) -> list[tuple[str, float, tuple | None]]:
        conditions: list = []
        for i in range(self._condition_list.count()):
            conditions.append(
                self._condition_list.item(i).data(Qt.ItemDataRole.UserRole)
            )
        return conditions

    def _on_paste_region(self) -> None:
        text = QApplication.clipboard().text().strip()
        parts = text.replace("，", ",").split(",")
        if len(parts) == 4:
            try:
                vals = [int(p.strip()) for p in parts]
                self._spin_rx.setValue(vals[0])
                self._spin_ry.setValue(vals[1])
                self._spin_rw.setValue(vals[2])
                self._spin_rh.setValue(vals[3])
                self._chk_region.setChecked(True)
            except ValueError:
                pass

    def _on_add_condition(self) -> None:
        idx = self._combo_template.currentIndex()
        if idx < 0:
            return
        template_key = self._combo_template.currentData()
        threshold = self._spin_threshold.value()
        region = (
            (
                self._spin_rx.value(),
                self._spin_ry.value(),
                self._spin_rw.value(),
                self._spin_rh.value(),
            )
            if self._chk_region.isChecked()
            else None
        )

        existing = self._get_existing_conditions()
        if self._presenter.check_duplicate(existing, template_key):
            log.warning(f"模板 [{template_key}] 已在列表中")
            return

        region_text = (
            f"区域:({region[0]},{region[1]},{region[2]}x{region[3]})"
            if region
            else "全屏"
        )
        item = QListWidgetItem(f"{template_key}  (阈值:{threshold:.2f})  {region_text}")
        item.setData(Qt.ItemDataRole.UserRole, (template_key, threshold, region))
        self._condition_list.addItem(item)
        log.debug(f"已添加 [{template_key}]，共 {self._condition_list.count()} 个条件")

    def _on_remove_condition(self) -> None:
        for item in self._condition_list.selectedItems():
            self._condition_list.takeItem(self._condition_list.row(item))
        log.debug(f"当前 {self._condition_list.count()} 个条件")

    def _on_clear_conditions(self) -> None:
        self._condition_list.clear()
        log.debug("已清除所有条件")

    # ---------- 检测 ----------

    def _on_detect(self) -> None:
        if self._condition_list.count() == 0:
            log.warning("请先添加至少一个检测条件")
            return
        if self._capture_widget is None:
            log.error("截图预览组件未初始化")
            return

        self._btn_detect.setEnabled(False)
        self._btn_detect.setText("检测中…")
        QApplication.processEvents()

        run_async(
            lambda: self._presenter.detect(self._get_existing_conditions()),
            on_result=self._on_detect_result,
            on_error=self._on_detect_error,
            parent=self,
        )

    def _on_detect_result(self, result) -> None:
        self._last_matches = result.last_matches
        pixmap = result.result.to_qpixmap()
        status = (
            "✓ 全部通过"
            if result.all_passed
            else f"✗ {result.passed_count}/{result.total}"
        )
        self._capture_widget.display_pixmap(pixmap, f"检测: {status}")
        self._btn_detect.setEnabled(True)
        self._btn_detect.setText("检测定位")

    def _on_detect_error(self, error: str) -> None:
        log.error(f"检测失败: {error}")
        self._btn_detect.setEnabled(True)
        self._btn_detect.setText("检测定位")

    def _on_condition_selected(
        self, current: QListWidgetItem | None, _prev: QListWidgetItem | None
    ) -> None:
        if current is None:
            return
        key = current.data(Qt.ItemDataRole.UserRole)[0]
        self._edit_display_name.setText(key)

    def _on_register_region(self) -> None:
        if not self._last_matches:
            log.warning("请先执行检测定位")
            return

        selected = self._condition_list.currentItem()
        if selected is None:
            log.warning("请先在条件列表中选中一项")
            return

        selected_key = selected.data(Qt.ItemDataRole.UserRole)[0]
        display_name = self._edit_display_name.text().strip()

        self._btn_register.setEnabled(False)
        self._btn_register.setText("注册中…")
        QApplication.processEvents()

        run_async(
            lambda: self._presenter.register_region(
                selected_key, self._last_matches, display_name
            ),
            on_result=self._on_register_result,
            on_error=self._on_register_error,
            parent=self,
        )

    def _on_register_result(self, result) -> None:
        self._edit_display_name.clear()
        self._refresh_template_list()
        if self._capture_widget is not None:
            self._capture_widget.clear()
        self._search_input.clear()
        self._last_matches.clear()
        self._btn_register.setEnabled(True)
        self._btn_register.setText("注册区域")

    def _on_register_error(self, error: str) -> None:
        log.error(f"注册失败: {error}")
        self._btn_register.setEnabled(True)
        self._btn_register.setText("注册区域")