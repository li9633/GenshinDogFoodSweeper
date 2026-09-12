"""Standalone Window 生命周期管理基类

为 UpdateWindow 等独立 QML Window 组件提供统一的创建/显示/关闭/复用逻辑。

用法:
    class MyWindowPresenter(WindowPresenter):
        _QML_PATH = "components/MyWindow.qml"

        def _on_before_create(self, win: QObject) -> None:
            win.someSignal.connect(self.onSomeAction)

子类只需覆写 _QML_PATH 和 _on_before_create 即可。
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from PySide6.QtCore import QObject, QUrl
from PySide6.QtQml import QQmlApplicationEngine, QQmlComponent
from utils.logger import log as logger


class WindowPresenter(QObject):
    """Standalone Window 生命周期管理基类"""

    # ── 子类覆写 ──
    _QML_PATH: ClassVar[str] = ""          # 相对于 QML_DIR 的组件路径
    _WINDOW_TITLE: ClassVar[str] = ""       # 窗口标题

    # ── 引擎注入（所有 WindowPresenter 子类共用） ──
    _engine: ClassVar[QQmlApplicationEngine | None] = None

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._window: QObject | None = None
        self._component: QQmlComponent | None = None

    # ════════════════════════════════════════════
    # 公开方法
    # ════════════════════════════════════════════

    def show_window(self) -> None:
        """显示窗口：已存在则聚焦，否则创建"""
        if self._window is not None:
            try:
                self._window.setProperty("visible", True)
                self._window.raise_()
                self._window.requestActivate()
                logger.debug(f"{self._QML_PATH} 已聚焦")
                return
            except RuntimeError:
                logger.debug(f"{self._QML_PATH} C++ 对象已销毁，重新创建")
                self._window = None
                self._component = None
        self._do_create()

    def close_window(self) -> None:
        """关闭窗口"""
        if self._window is not None:
            self._window.close()

    # ════════════════════════════════════════════
    # 子类钩子
    # ════════════════════════════════════════════

    def _on_before_create(self, win: QObject) -> None:
        """QML 窗口创建后、显示前的初始化（子类覆写，连接信号等）"""
        raise NotImplementedError  # noqa: RET606

    def _on_closing(self) -> None:
        """窗口关闭时清理引用（子类可覆写扩展）"""
        self._window = None
        self._component = None

    # ════════════════════════════════════════════
    # 引擎注入（类方法，供 registry.py 调用）
    # ════════════════════════════════════════════

    @classmethod
    def set_engine(cls, engine: QQmlApplicationEngine) -> None:
        """在 main.py/registry.py 中调用一次，注入 QML 引擎引用。"""
        cls._engine = engine

    # ════════════════════════════════════════════
    # 内部
    # ════════════════════════════════════════════

    def _do_create(self) -> None:
        engine = self._get_engine()
        if engine is None:
            return

        from common.paths import QML_DIR

        qml_path = Path(str(QML_DIR)) / self._QML_PATH
        logger.debug(f"加载 Window 组件: {qml_path}")

        component = QQmlComponent(engine, QUrl.fromLocalFile(str(qml_path)))
        if component.isError():
            logger.warning(f"组件加载失败: {component.errorString()}")
            return

        win = component.create()
        if win is None:
            logger.warning(f"组件创建失败: {component.errorString()}")
            return

        win.setProperty("title", self._WINDOW_TITLE)
        win.closing.connect(self._on_closing)
        self._on_before_create(win)

        self._window = win
        self._component = component  # 防止 GC 连带销毁
        win.setProperty("visible", True)
        logger.debug(f"{self._QML_PATH} 已显示")

    def _get_engine(self) -> QQmlApplicationEngine | None:
        engine = self.__class__._engine
        if engine is None:
            logger.warning(f"{self.__class__.__name__}._engine 未注入，无法创建窗口")
        return engine