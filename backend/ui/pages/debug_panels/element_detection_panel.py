"""元素定位检测面板 — 独立调试子组件"""

from __future__ import annotations

import time

import cv2
import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
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
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from backend.automation.template_manager import TemplateManager
from backend.utils.screen_capture import ScreenshotCapture


class ElementDetectionPanel(QGroupBox):
    """元素定位检测 — 模板匹配 + 可视化标记"""

    def __init__(self, capture_widget: QWidget | None = None, parent=None):
        super().__init__("元素定位检测", parent)
        self._capture_widget = capture_widget
        self._last_matches: list[tuple[str, int, int, int, int]] = []
        self._build_ui()
        self._refresh_template_list()

    # ---------- UI ----------

    def _build_ui(self) -> None:
        layout = QVBoxLayout()
        self.setLayout(layout)

        add_group = QGroupBox("添加检测条件")
        add_layout = QVBoxLayout()
        add_group.setLayout(add_layout)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("搜索:"))
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("输入关键词筛选模板…")
        self._search_input.textChanged.connect(self._on_search_changed)
        row1.addWidget(self._search_input)
        self._btn_refresh = QPushButton("刷新")
        self._btn_refresh.clicked.connect(self._on_refresh)
        row1.addWidget(self._btn_refresh)
        add_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("模板:"))
        self._combo_template = QComboBox()
        self._combo_template.setMinimumWidth(150)
        self._combo_template.currentIndexChanged.connect(self._on_template_changed)
        row2.addWidget(self._combo_template, stretch=1)
        row2.addWidget(QLabel("阈值:"))
        self._spin_threshold = QDoubleSpinBox()
        self._spin_threshold.setRange(0.0, 1.0)
        self._spin_threshold.setSingleStep(0.05)
        self._spin_threshold.setValue(0.80)
        self._spin_threshold.setDecimals(2)
        row2.addWidget(self._spin_threshold)
        self._btn_add = QPushButton("+ 添加")
        self._btn_add.clicked.connect(self._on_add_condition)
        row2.addWidget(self._btn_add)
        add_layout.addLayout(row2)

        region_row = QHBoxLayout()
        self._chk_region = QCheckBox("限定区域")
        region_row.addWidget(self._chk_region)
        region_row.addWidget(QLabel("X:"))
        self._spin_rx = QSpinBox()
        self._spin_rx.setRange(0, 9999)
        region_row.addWidget(self._spin_rx)
        region_row.addWidget(QLabel("Y:"))
        self._spin_ry = QSpinBox()
        self._spin_ry.setRange(0, 9999)
        region_row.addWidget(self._spin_ry)
        region_row.addWidget(QLabel("宽:"))
        self._spin_rw = QSpinBox()
        self._spin_rw.setRange(1, 9999)
        self._spin_rw.setValue(200)
        region_row.addWidget(self._spin_rw)
        region_row.addWidget(QLabel("高:"))
        self._spin_rh = QSpinBox()
        self._spin_rh.setRange(1, 9999)
        self._spin_rh.setValue(100)
        region_row.addWidget(self._spin_rh)
        self._btn_paste = QPushButton("粘贴")
        self._btn_paste.clicked.connect(self._on_paste_region)
        region_row.addWidget(self._btn_paste)
        region_row.addStretch()
        add_layout.addLayout(region_row)

        layout.addWidget(add_group)

        list_group = QGroupBox("检测条件列表（全部匹配才算通过）")
        list_layout = QVBoxLayout()
        list_group.setLayout(list_layout)

        self._condition_list = QListWidget()
        self._condition_list.setMaximumHeight(120)
        self._condition_list.currentItemChanged.connect(self._on_condition_selected)
        list_layout.addWidget(self._condition_list)

        btn_row = QHBoxLayout()
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
        reg_row.addWidget(QLabel("显示名称:"))
        self._edit_display_name = QLineEdit()
        self._edit_display_name.setPlaceholderText("留空则使用文件名")
        reg_row.addWidget(self._edit_display_name)
        self._btn_register = QPushButton("注册区域")
        self._btn_register.clicked.connect(self._on_register_region)
        reg_row.addWidget(self._btn_register)
        layout.addLayout(reg_row)

        self._label_result = QLabel("请添加检测条件后点击检测…")
        self._label_result.setProperty("class", "hint")
        layout.addWidget(self._label_result)

    # ---------- 模板列表 ----------

    def _refresh_template_list(self, keyword: str = "") -> None:
        self._combo_template.clear()
        templates = (
            TemplateManager.search(keyword) if keyword else TemplateManager.list_all()
        )
        for key, filename in templates.items():
            self._combo_template.addItem(f"{key} ({filename})", key)

    def _on_refresh(self) -> None:
        TemplateManager.reload()
        self._refresh_template_list()

    def _on_search_changed(self, text: str) -> None:
        self._refresh_template_list(text.strip())

    # ---------- 条件管理 ----------

    def _on_template_changed(self, _idx: int) -> None:
        key = self._combo_template.currentData()
        if not key:
            return
        region = TemplateManager.get_region(key)
        if region:
            self._spin_rx.setValue(region[0])
            self._spin_ry.setValue(region[1])
            self._spin_rw.setValue(region[2])
            self._spin_rh.setValue(region[3])
            self._chk_region.setChecked(True)
        else:
            self._chk_region.setChecked(False)

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
        region = None
        if self._chk_region.isChecked():
            region = (self._spin_rx.value(), self._spin_ry.value(),
                      self._spin_rw.value(), self._spin_rh.value())

        for i in range(self._condition_list.count()):
            existing_key = self._condition_list.item(i).data(Qt.ItemDataRole.UserRole)[0]
            if existing_key == template_key:
                self._label_result.setText(f"⚠ 模板 [{template_key}] 已在列表中")
                return

        region_text = f"区域:({region[0]},{region[1]},{region[2]}x{region[3]})" if region else "全屏"
        item = QListWidgetItem(
            f"{template_key}  (阈值:{threshold:.2f})  {region_text}"
        )
        item.setData(Qt.ItemDataRole.UserRole, (template_key, threshold, region))
        self._condition_list.addItem(item)
        self._label_result.setText(
            f"已添加 [{template_key}]，共 {self._condition_list.count()} 个条件"
        )

    def _on_remove_condition(self) -> None:
        for item in self._condition_list.selectedItems():
            self._condition_list.takeItem(self._condition_list.row(item))
        self._label_result.setText(f"当前 {self._condition_list.count()} 个条件")

    def _on_clear_conditions(self) -> None:
        self._condition_list.clear()
        self._label_result.setText("请添加检测条件后点击检测…")

    # ---------- 检测逻辑 ----------

    def _on_detect(self) -> None:
        if self._condition_list.count() == 0:
            self._label_result.setText("X 请先添加至少一个检测条件")
            return
        if self._capture_widget is None:
            self._label_result.setText("X 截图预览组件未初始化")
            return

        conditions: list[tuple[str, float, tuple[int, int, int, int] | None]] = []
        for i in range(self._condition_list.count()):
            conditions.append(
                self._condition_list.item(i).data(Qt.ItemDataRole.UserRole)
            )

        self._btn_detect.setEnabled(False)
        self._btn_detect.setText("检测中…")

        try:
            cap = ScreenshotCapture()
            result = cap.capture()
            full_gray = cv2.cvtColor(result.image, cv2.COLOR_RGB2GRAY)

            t0 = time.perf_counter()
            all_passed = True
            detail_parts: list[str] = []
            self._last_matches.clear()

            for template_key, threshold, region in conditions:
                template_path = TemplateManager.get_path(template_key)
                if template_path is None:
                    detail_parts.append(f"{template_key}: 文件不存在")
                    all_passed = False
                    continue

                template = cv2.imread(str(template_path), cv2.IMREAD_GRAYSCALE)
                if template is None:
                    detail_parts.append(f"{template_key}: 加载失败")
                    all_passed = False
                    continue

                orig_th, orig_tw = template.shape

                if region:
                    rx, ry, rw, rh = region
                    search_area = full_gray[ry:ry + rh, rx:rx + rw]
                    if search_area.size == 0:
                        detail_parts.append(f"{template_key}: 搜索区域无效")
                        all_passed = False
                        continue
                else:
                    rx, ry = 0, 0
                    search_area = full_gray

                best_score, best_loc, best_scale, best_size = \
                    self._multi_scale_match(search_area, template)

                passed = best_score >= threshold
                if not passed:
                    all_passed = False

                color = (0, 255, 0) if passed else (255, 0, 0)
                tw, th = best_size
                if best_scale >= 1.0:
                    size_info = f"{tw}x{th}"
                else:
                    size_info = f"{tw}x{th}/{orig_tw}x{orig_th}"
                result.draw_rect(
                    best_loc[0] + rx, best_loc[1] + ry, tw, th,
                    color=color, thickness=3,
                    label=f"{template_key} {best_score:.2f}",
                )
                detail_parts.append(
                    f"{'✓' if passed else '✗'}{template_key}: {best_score:.3f}@{best_scale:.2f}x ({size_info}) → ({best_loc[0] + rx},{best_loc[1] + ry})"
                )

                self._last_matches.append(
                    (template_key, best_loc[0] + rx, best_loc[1] + ry, tw, th)
                )

            elapsed = (time.perf_counter() - t0) * 1000

            passed_count = sum(1 for p in detail_parts if p.startswith("✓"))
            total = len(conditions)

            timing = f" ({elapsed:.0f}ms)"
            if all_passed:
                self._label_result.setText(
                    f"✓ 全部通过 ({passed_count}/{total}){timing} | "
                    + " | ".join(detail_parts)
                )
            else:
                self._label_result.setText(
                    f"✗ 未通过 ({passed_count}/{total}){timing} | "
                    + " | ".join(detail_parts)
                )

            pixmap = result.to_qpixmap()
            status = "✓ 全部通过" if all_passed else f"✗ {passed_count}/{total}"
            self._capture_widget.display_pixmap(pixmap, f"检测: {status}")

        except RuntimeError as e:
            self._label_result.setText(f"X 截图失败: {e}")
        finally:
            self._btn_detect.setEnabled(True)
            self._btn_detect.setText("检测定位")

    def _on_condition_selected(self, current: QListWidgetItem | None, _prev: QListWidgetItem | None) -> None:
        if current is None:
            return
        key = current.data(Qt.ItemDataRole.UserRole)[0]
        self._edit_display_name.setText(key)

    def _on_register_region(self) -> None:
        if not self._last_matches:
            self._label_result.setText("X 请先执行检测定位")
            return

        selected = self._condition_list.currentItem()
        if selected is None:
            self._label_result.setText("X 请先在条件列表中选中一项")
            return

        selected_key = selected.data(Qt.ItemDataRole.UserRole)[0]

        match = next(
            (m for m in self._last_matches if m[0] == selected_key), None
        )
        if match is None:
            self._label_result.setText(f"X [{selected_key}] 本次未匹配成功")
            return

        _, x, y, w, h = match
        display_name = self._edit_display_name.text().strip()
        name = display_name if display_name else selected_key

        entry = TemplateManager._find_entry(selected_key)
        filename = str(entry["file"]) if entry and entry.get("file") else f"images/{selected_key}.png"
        TemplateManager.register(name, filename, (x, y, w, h))

        TemplateManager.save()
        self._edit_display_name.clear()
        self._label_result.setText(f"✓ [{name}] 区域已注册: ({x},{y},{w}x{h})")

        self._refresh_template_list()
        if self._capture_widget is not None:
            self._capture_widget.clear()
        self._search_input.clear()
        self._last_matches.clear()

    @staticmethod
    def _multi_scale_match(
        screen_gray: np.ndarray,
        template: np.ndarray,
        scales: tuple[float, ...] = (0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.5),
    ) -> tuple[float, tuple[int, int], float, tuple[int, int]]:
        """多尺度模板匹配，返回 (最高分, 位置, 缩放比, 模板尺寸)"""
        best_score = -1.0
        best_loc = (0, 0)
        best_scale = 1.0
        best_size = template.shape[::-1]

        th, tw = template.shape
        sh, sw = screen_gray.shape

        for scale in scales:
            new_w = int(tw * scale)
            new_h = int(th * scale)
            if new_w > sw or new_h > sh or new_w < 5 or new_h < 5:
                continue
            scaled = cv2.resize(template, (new_w, new_h))
            match_result = cv2.matchTemplate(screen_gray, scaled, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(match_result)
            if max_val > best_score:
                best_score = float(max_val)
                best_loc = max_loc
                best_scale = scale
                best_size = (new_w, new_h)

        return best_score, best_loc, best_scale, best_size