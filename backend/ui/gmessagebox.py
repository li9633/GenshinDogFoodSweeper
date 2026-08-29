"""GMessageBox Python API
=======================
通过信号桥接触发 QML 侧的 GMessageBox 弹窗，提供简洁的静态方法调用：

    from ui.gmessagebox import GMessageBox
    GMessageBox.init(engine)          # 在 main.py 中初始化一次
    GMessageBox.error("错误消息")      # 任意位置调用
    GMessageBox.warning("警告消息")
    GMessageBox.info("提示消息")
    GMessageBox.success("成功消息")

实现原理：
- GMessageBoxBridge 是注册到 QML 的 QObject，携带 showMessage 信号
- MainWindow.qml 中声明 GMessageBox 并通过 Connections 监听该信号
- Python 侧调用 GMessageBox.error() → 发射信号 → QML 打开 Dialog
"""

from __future__ import annotations

import ctypes
import json
from collections import deque
from collections.abc import Callable
from ctypes import wintypes
from dataclasses import dataclass, field
from typing import ClassVar

from PySide6.QtCore import QObject, QTimer, Signal, Slot
from PySide6.QtQml import QQmlApplicationEngine
from utils.logger import log

# ---- Windows API 常量 ----
_SWP_NOMOVE = 0x0002
_SWP_NOSIZE = 0x0001
_SWP_SHOWWINDOW = 0x0040
_HWND_TOPMOST = -1
_HWND_NOTOPMOST = -2


def _force_foreground(hwnd: int) -> None:
    """使用 Windows API 强制将窗口拉到前台（绕过前台锁定）

    Windows 默认禁止后台进程通过 SetForegroundWindow 抢焦点，
    但先设为 TOPMOST 再调用 SetForegroundWindow 可以绕过此限制。
    """
    user32 = ctypes.windll.user32
    user32.SetWindowPos(
        wintypes.HWND(hwnd), wintypes.HWND(_HWND_TOPMOST),
        0, 0, 0, 0, _SWP_NOMOVE | _SWP_NOSIZE | _SWP_SHOWWINDOW,
    )
    user32.SetForegroundWindow(wintypes.HWND(hwnd))
    user32.SetWindowPos(
        wintypes.HWND(hwnd), wintypes.HWND(_HWND_NOTOPMOST),
        0, 0, 0, 0, _SWP_NOMOVE | _SWP_NOSIZE,
    )


def _make_dispatch(
    on_confirm: Callable[[], None] | None,
    on_cancel: Callable[[], None] | None,
) -> Callable[[str], None]:
    """将 confirm 风格的回调转为 on_button 分发器"""
    def dispatch(role: str) -> None:
        if role == "accept" and on_confirm:
            on_confirm()
        elif role == "reject" and on_cancel:
            on_cancel()
    return dispatch


@dataclass
class Button:
    """按钮定义"""
    text: str
    role: str = "accept"
    color_type: str = "primary"

    def to_dict(self) -> dict:
        return {"text": self.text, "role": self.role, "colorType": self.color_type}


@dataclass
class _DialogRequest:
    """内部队列项，统一表示一个待显示的弹窗"""
    msg_type: str
    msg: str
    title: str = ""
    buttons: list[dict] = field(default_factory=list)
    bring_to_front: bool = False
    on_button: Callable[[str], None] | None = None


class GMessageBoxBridge(QObject):
    """信号桥：Python → QML，触发 GMessageBox 弹窗

    内置弹窗队列：当多个弹窗同时触发时，只显示当前一个，
    其余排队。用户关闭当前弹窗后自动显示下一个。
    """

    showMessage = Signal(str, str, bool)  # (msgType, msgText, bringToFront)
    showDialog = Signal(str, str, str, bool, str)  # (msgType, title, msgText, bringToFront, buttonsJson)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._on_button: Callable[[str], None] | None = None
        self._is_showing: bool = False
        self._pending: deque[_DialogRequest] = deque()

    def _emit_request(self, req: _DialogRequest) -> None:
        """发射信号，显示弹窗"""
        self._on_button = req.on_button
        if req.buttons:
            self.showDialog.emit(
                req.msg_type, req.title, req.msg, req.bring_to_front,
                json.dumps(req.buttons, ensure_ascii=False),
            )
        else:
            self.showMessage.emit(req.msg_type, req.msg, req.bring_to_front)

    def _show_or_queue(self, req: _DialogRequest) -> None:
        """显示弹窗或加入队列"""
        if self._is_showing:
            self._pending.append(req)
        else:
            self._is_showing = True
            self._emit_request(req)

    def _dequeue_and_show(self) -> None:
        """从队列取出下一个弹窗并显示"""
        if self._pending:
            req = self._pending.popleft()
            self._is_showing = True
            self._emit_request(req)

    @Slot(str)
    def handleButtonClicked(self, role: str) -> None:
        cb = self._on_button
        self._on_button = None
        self._is_showing = False
        if cb:
            cb(role)
        # 延迟到下一事件循环：等当前 Popup 关闭动画完成后再出队
        QTimer.singleShot(0, self._dequeue_and_show)


class GMessageBox:
    """GMessageBox 调用入口（静态方法）"""

    Button = Button  # 暴露 Button 为 GMessageBox.Button

    _bridge: ClassVar[GMessageBoxBridge | None] = None
    _main_hwnd: ClassVar[int | None] = None

    @classmethod
    def init(cls, engine: QQmlApplicationEngine) -> None:
        """初始化：在 main.py 中调用一次，传入 QML 引擎"""
        # 从 QML 上下文获取已注册的 GMessageBoxBridge
        bridge = engine.rootContext().contextProperty("GMessageBoxBridge")
        if bridge is not None:
            cls._bridge = bridge
        else:
            log.error("GMessageBoxBridge 未在 QML 上下文中找到")

        # 获取主窗口 HWND，用于 Windows API 强制前台
        root_objects = engine.rootObjects()
        if root_objects:
            cls._main_hwnd = int(root_objects[0].winId())

    @classmethod
    def error(cls, msg: str, bring_to_front: bool = True) -> None:
        cls._show("error", msg, bring_to_front)

    @classmethod
    def warning(cls, msg: str, bring_to_front: bool = True) -> None:
        cls._show("warning", msg, bring_to_front)

    @classmethod
    def info(cls, msg: str, bring_to_front: bool = False) -> None:
        cls._show("info", msg, bring_to_front)

    @classmethod
    def success(cls, msg: str, bring_to_front: bool = False) -> None:
        cls._show("success", msg, bring_to_front)

    # ============================================================
    # 自定义按钮 API
    # ============================================================

    @classmethod
    def show(
        cls,
        msg_type: str,
        msg: str,
        *,
        title: str = "",
        buttons: list[Button] | None = None,
        bring_to_front: bool = False,
        on_button: Callable[[str], None] | None = None,
    ) -> None:
        """通用弹窗，支持任意数量自定义按钮。

        Args:
            on_button: 按钮回调，接收 role 字符串。
                       可通过 role 分发不同操作：
                       lambda role: {"retry": do_retry, "skip": do_skip}.get(role, lambda: None)()

        Example:
            GMessageBox.show(
                "warning", "同步失败，请选择操作",
                buttons=[
                    GMessageBox.Button("重试", "retry"),
                    GMessageBox.Button("跳过", "skip"),
                    GMessageBox.Button("取消", "cancel"),
                ],
                on_button=lambda role: {
                    "retry": do_retry,
                    "skip": do_skip,
                }[role](),
            )
        """
        if cls._bridge is None:
            log.error("GMessageBox 未初始化，调用 init() 后再使用")
            return

        if bring_to_front and cls._main_hwnd is not None:
            _force_foreground(cls._main_hwnd)

        btn_list = [b.to_dict() for b in (buttons or [])]
        cls._bridge._show_or_queue(
            _DialogRequest(
                msg_type=msg_type, msg=msg, title=title,
                buttons=btn_list, bring_to_front=bring_to_front,
                on_button=on_button,
            )
        )

    @classmethod
    def confirm(
        cls,
        msg: str,
        *,
        title: str = "确认",
        confirm_text: str = "确定",
        cancel_text: str = "取消",
        confirm_color: str = "primary",
        cancel_color: str = "secondary",
        on_confirm: Callable[[], None] | None = None,
        on_cancel: Callable[[], None] | None = None,
    ) -> None:
        """确认对话框快捷方法。

        Example:
            GMessageBox.confirm(
                "确定要清空所有数据吗？",
                confirm_text="确定清空", confirm_color="danger",
                on_confirm=lambda: clear_all(),
            )
        """
        cls.show(
            "warning", msg,
            title=title,
            buttons=[
                Button(confirm_text, "accept", confirm_color),
                Button(cancel_text, "reject", cancel_color),
            ],
            bring_to_front=True,
            on_button=_make_dispatch(on_confirm, on_cancel),
        )

    # ---------- 内部实现 ----------

    @classmethod
    def _show(cls, msg_type: str, msg: str, bring_to_front: bool) -> None:
        if cls._bridge is None:
            log.error("GMessageBox 未初始化，请先调用 GMessageBox.init(engine)")
            return
        if bring_to_front and cls._main_hwnd is not None:
            _force_foreground(cls._main_hwnd)
        cls._bridge._show_or_queue(
            _DialogRequest(msg_type=msg_type, msg=msg, bring_to_front=bring_to_front)
        )