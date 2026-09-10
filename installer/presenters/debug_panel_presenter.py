"""调试面板 Presenter
=================
DebugPanel.qml 的专属 Presenter，负责：
- 页面列表（含可用性计算）
- 模式列表
- 调试信息格式化
- 所有操作代理到 DebugPresenter

QML 层只做数据绑定，零业务逻辑。
"""

from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot

from installer.presenters.debug_presenter import DebugPresenter

# 页面定义：(key, label) — 顺序即显示顺序
_PAGE_DEFS: list[tuple[str, str]] = [
    ("welcome", "W"),
    ("directory", "D"),
    ("confirm", "C"),
    ("progress", "P"),
    ("finish", "F"),
]

# 仅在卸载模式下可用的页面
_UNINSTALL_ONLY_PAGES = {"confirm"}
# 在卸载模式下不可用的页面
_NOT_UNINSTALL_PAGES = {"welcome", "directory"}

# 模式定义：(key, label, color)
_MODE_DEFS: list[tuple[str, str, str]] = [
    ("install", "安装", "#1976D2"),
    ("update", "更新", "#4CAF50"),
    ("uninstall", "卸载", "#D32F2F"),
]


class DebugPanelPresenter(QObject):
    """调试面板专属 Presenter — QML 只绑定此类属性，不做任何计算。"""

    panelsChanged = Signal()

    def __init__(self, dp: DebugPresenter, parent: QObject | None = None):
        super().__init__(parent)
        self._dp = dp
        dp.stateChanged.connect(self._refresh)

        # 构建页面数据（key, label, enabled）
        self._pages: list[dict] = []
        # 构建模式数据（key, label, color）
        self._modes = [
            {"key": k, "label": l, "color": c} for k, l, c in _MODE_DEFS
        ]
        self._refresh()

    # ========== 内部逻辑 ==========

    def _refresh(self) -> None:
        mode = self._dp.mode
        self._pages = [
            {
                "key": key,
                "label": label,
                "enabled": self._is_page_enabled(key, mode),
            }
            for key, label in _PAGE_DEFS
        ]
        self.panelsChanged.emit()

    @staticmethod
    def _is_page_enabled(page_key: str, mode: str) -> bool:
        if page_key in _UNINSTALL_ONLY_PAGES:
            return mode == "uninstall"
        if page_key in _NOT_UNINSTALL_PAGES:
            return mode != "uninstall"
        return True

    # ========== 页面列表（QML 绑定） ==========

    @Property("QVariantList", notify=panelsChanged)
    def pages(self) -> list[dict]:
        return self._pages

    # ========== 模式列表（QML 绑定） ==========

    @Property("QVariantList", notify=panelsChanged)
    def modes(self) -> list[dict]:
        return self._modes

    # ========== 当前状态 ==========

    @Property(str, notify=panelsChanged)
    def currentPage(self) -> str:
        return self._dp.current_page

    @Property(str, notify=panelsChanged)
    def currentMode(self) -> str:
        return self._dp.mode

    @Property(bool, notify=panelsChanged)
    def quickUpdate(self) -> bool:
        return self._dp.quick_update

    # ========== 调试信息（格式化在 Python 侧） ==========

    @Property(str, notify=panelsChanged)
    def debugInfo(self) -> str:
        dp = self._dp
        return (
            f"页面: {dp.current_page}\n"
            f"模式: {dp.mode}\n"
            f"快速更新: {dp.quick_update}\n"
            f"安装目录: {dp.install_dir}\n"
            f"当前版本: {dp.version}\n"
            f"旧版本: {dp.old_version}\n"
            f"accentColor: {dp.accent_color}\n"
            f"allowClose: {dp.allow_close}"
        )

    # ========== 操作（代理到 DebugPresenter） ==========

    @Slot(str)
    def navigateTo(self, page: str) -> None:
        self._dp.navigateTo(page)

    @Slot(str)
    def setMode(self, value: str) -> None:
        self._dp.setMode(value)

    @Slot(bool)
    def setQuickUpdate(self, value: bool) -> None:
        self._dp.setQuickUpdate(value)