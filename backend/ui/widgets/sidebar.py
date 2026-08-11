"""
侧边栏导航组件
==============
基于 QTreeWidget 实现多级可展开/折叠菜单（Vue3 el-menu 风格）。
接收 nav_items 层级数据 → 渲染树形菜单 → 点击叶子节点 emit page_selected 信号。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)


@dataclass
class NavItem:
    """导航项（支持多级菜单）

    children 为空列表 → 叶子节点（点击触发页面切换）；
    children 非空 → 父节点（点击展开/折叠子菜单）。
    """

    key: str
    label: str
    children: list[NavItem] = field(default_factory=list)


class Sidebar(QWidget):
    """侧边栏导航组件

    Props（构造参数）:
        nav_items: 导航项层级列表
        width: 侧边栏宽度，默认 160

    Emits:
        page_selected(key): 用户点击叶子节点时触发
    """

    page_selected = pyqtSignal(str)

    def __init__(
        self,
        nav_items: list[NavItem],
        width: int = 160,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._item_map: dict[str, QTreeWidgetItem] = {}

        self.setFixedWidth(width)
        self._build_ui(nav_items)

    # ---------- 公开方法 ----------

    def set_active(self, key: str) -> None:
        """高亮指定导航项，自动展开所有祖先节点"""
        item = self._item_map.get(key)
        if item is None:
            return

        parent = item.parent()
        while parent:
            self._tree.expandItem(parent)
            parent = parent.parent()

        self._tree.setCurrentItem(item)

    # ---------- UI 构建 ----------

    def _build_ui(self, nav_items: list[NavItem]) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setIndentation(16)
        self._tree.setAnimated(True)
        self._tree.setRootIsDecorated(True)
        self._tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._tree.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._tree.setExpandsOnDoubleClick(False)
        self._tree.setProperty("class", "nav-tree")

        self._build_items(nav_items, self._tree)
        self._tree.itemClicked.connect(self._on_item_clicked)

        layout.addWidget(self._tree)

    def _build_items(
        self, items: list[NavItem], parent: QTreeWidget | QTreeWidgetItem
    ) -> None:
        for nav_item in items:
            tree_item = QTreeWidgetItem(parent)
            tree_item.setText(0, f"  {nav_item.label}")
            tree_item.setData(0, Qt.ItemDataRole.UserRole, nav_item.key)
            self._item_map[nav_item.key] = tree_item

            if nav_item.children:
                self._build_items(nav_item.children, tree_item)

    # ---------- 交互 ----------

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        key = item.data(0, Qt.ItemDataRole.UserRole)
        if key is None:
            return

        # 叶子节点 → emit 信号；父节点 → QTreeWidget 自动处理展开/折叠
        if item.childCount() == 0:
            self.page_selected.emit(key)