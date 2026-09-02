"""
输入调试 Presenter
==================
直接包装 WindowHelper 和 MouseController 底层模块，
供 QML 调试面板绑定，用于测试窗口聚焦、鼠标移动、点击、滚轮等操作。
"""

from __future__ import annotations

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot
from utils.logger import log

from backend.automation.mouse_controller import MouseController
from backend.automation.window_helper import WindowHelper


class InputDebugPresenter(QObject):
    """输入调试 Presenter — 直接对底层 WindowHelper / MouseController 进行调试"""

    windowInfoChanged = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._win = WindowHelper()
        MouseController.set_window_helper(self._win)

        self._win_origin_x = 0
        self._win_origin_y = 0
        self._win_hwnd = 0
        self._screen_w, self._screen_h = MouseController.screen_size()
        self._is_admin = MouseController.is_admin()

        self._timer = QTimer(self)
        self._timer.setInterval(2000)
        self._timer.timeout.connect(self._refresh_window_info)
        self._timer.start()
        self._refresh_window_info()

    def _refresh_window_info(self) -> None:
        """刷新窗口信息（原点、句柄），窗口不存在时重置为零"""
        info = self._win.get_window_info()
        if info is None:
            if self._win_origin_x != 0 or self._win_origin_y != 0:
                self._win_origin_x = 0
                self._win_origin_y = 0
                self._win_hwnd = 0
                self.windowInfoChanged.emit()
            return

        ox, oy = info.left, info.top
        hwnd = info.hwnd or 0

        changed = False
        if ox != self._win_origin_x or oy != self._win_origin_y:
            self._win_origin_x = ox
            self._win_origin_y = oy
            changed = True
        if hwnd != self._win_hwnd:
            self._win_hwnd = hwnd
            changed = True
        if changed:
            self.windowInfoChanged.emit()

    # ========== WindowHelper Properties ==========

    @Property(int, notify=windowInfoChanged)
    def winOriginX(self) -> int:
        return self._win_origin_x

    @Property(int, notify=windowInfoChanged)
    def winOriginY(self) -> int:
        return self._win_origin_y

    @Property(int, notify=windowInfoChanged)
    def winHwnd(self) -> int:
        return self._win_hwnd

    @Property(bool, notify=windowInfoChanged)
    def isWindowFound(self) -> bool:
        return self._win_origin_x > 0 or self._win_origin_y > 0

    # ========== MouseController Properties ==========

    @Property(int, constant=True)
    def screenWidth(self) -> int:
        return self._screen_w

    @Property(int, constant=True)
    def screenHeight(self) -> int:
        return self._screen_h

    @Property(bool, constant=True)
    def isAdmin(self) -> bool:
        return self._is_admin

    # ========== WindowHelper Slots ==========

    @Slot()
    def focusWindow(self) -> None:
        """聚焦原神窗口"""
        try:
            ok = self._win.focus()
            log.info(f"聚焦窗口: {'成功' if ok else '失败'}")
        except Exception as e:
            log.warning(f"聚焦窗口异常: {e}")

    @Slot()
    def refreshWindowInfo(self) -> None:
        """手动刷新窗口信息"""
        self._refresh_window_info()

    # ========== MouseController Slots ==========

    @Slot(int, int)
    def moveTo(self, x: int, y: int) -> None:
        """移动鼠标到窗口相对坐标 (x, y)，MouseController 自动转换为屏幕绝对坐标"""
        ok = MouseController.move_to(x, y)
        if not ok:
            log.warning(f"移动失败: ({x}, {y})")

    @Slot()
    def click(self) -> None:
        """在当前位置点击左键"""
        MouseController.click()

    @Slot(int, int)
    def moveAndClick(self, x: int, y: int) -> None:
        """移动鼠标到窗口相对坐标 (x, y) 并点击"""
        MouseController.move_and_click(x, y)

    @Slot(int)
    def scroll(self, clicks: int) -> None:
        """滚轮滚动，正数向上，负数向下"""
        MouseController.scroll(clicks)

    @Slot(int, int, int, int, int, int)
    def drag(
        self,
        from_x: int,
        from_y: int,
        to_x: int,
        to_y: int,
        steps: int = 10,
        step_delay_ms: int = 10,
    ) -> None:
        """鼠标拖拽：从 (from_x, from_y) 拖到 (to_x, to_y)"""
        MouseController.drag(from_x, from_y, to_x, to_y, steps, step_delay_ms)