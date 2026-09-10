"""调试 Presenter
=========
仅在 GDFS_INSTALLER_DEBUG=True 时创建，包装 Coordinator 暴露调试接口。
Coordinator 本身零改动，所有调试逻辑集中于此。
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot

from installer.presenters.coordinator import AppCoordinator


class DebugPresenter(QObject):
    """包装 Coordinator，提供调试专用数据查询与操作接口。"""

    stateChanged = Signal()

    def __init__(self, coordinator: AppCoordinator, parent: QObject | None = None):
        super().__init__(parent)
        self._coord = coordinator
        self._current_page = "welcome"

        coordinator.modeChanged.connect(self.stateChanged)
        coordinator.installDirChanged.connect(self.stateChanged)
        coordinator.quickUpdateChanged.connect(self.stateChanged)
        coordinator.oldVersionChanged.connect(self.stateChanged)
        coordinator.navigateRequested.connect(self._on_navigate)

    def _on_navigate(self, page: str) -> None:
        self._current_page = page
        self.stateChanged.emit()

    # ========== 数据查询（供 DebugPanelPresenter 调用） ==========

    @property
    def current_page(self) -> str:
        return self._current_page

    @property
    def mode(self) -> str:
        return self._coord.mode

    @property
    def install_dir(self) -> str:
        return self._coord.install_dir

    @property
    def version(self) -> str:
        return self._coord.version

    @property
    def old_version(self) -> str:
        return self._coord.old_version

    @property
    def quick_update(self) -> bool:
        return self._coord.quick_update

    @property
    def accent_color(self) -> str:
        return self._coord.accentColor

    @property
    def allow_close(self) -> bool:
        return self._coord.allowClose

    # ========== 调试操作（供 DebugPanelPresenter 代理） ==========

    @Slot(str)
    def setMode(self, value: str) -> None:
        self._coord.mode = value

    @Slot(bool)
    def setQuickUpdate(self, value: bool) -> None:
        self._coord.quick_update = value

    @Slot(str)
    def navigateTo(self, page: str) -> None:
        self._coord.navigate_to(page)