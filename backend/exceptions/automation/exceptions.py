"""自动化层异常定义

设计约定：异常只承载“给用户看的消息”（``_MESSAGE``），构造时只写日志，
**不弹窗、不碰 UI** —— 展示由 UI 层决定（Presenter / lifecycle），
这样领域层不反向依赖界面层，也不会因为 ``raise`` 就产生副作用。
"""

from backend.utils.logger import log


class OcrModelNotReadyError(RuntimeError):
    """OCR 模型未就绪异常

    构造时只记录日志；界面提示由 UI 层负责（例如 ui/lifecycle 在窗口就绪
    阶段弹一次提示，扫描 worker 通过 errorOccurred 上报）。
    """

    _MESSAGE = "OCR 模型未下载，请前往「设置」-> [模型] -> 点击「下载模型」"

    def __init__(self) -> None:
        super().__init__(self._MESSAGE)
        log.error(self._MESSAGE)


# 窗口未找到的两种场景消息（screen_capture 判断场景，exception_handler 过滤 QML 日志）
WINDOW_NOT_FOUND_PROCESS_MSG = "请先启动原神游戏"
WINDOW_NOT_FOUND_MINIMIZED_MSG = "请将原神窗口置于前台"


class GameWindowNotFoundError(RuntimeError):
    """游戏窗口未找到异常

    由调用方（screen_capture / window_helper）根据进程状态传入对应消息：
    - ``WINDOW_NOT_FOUND_PROCESS_MSG``    → 进程未启动
    - ``WINDOW_NOT_FOUND_MINIMIZED_MSG``  → 窗口不可见
    """

    _MESSAGE = WINDOW_NOT_FOUND_PROCESS_MSG  # 用于 exception_handler 匹配

    def __init__(self, message: str = "") -> None:
        msg = message or self._MESSAGE
        super().__init__(msg)
        log.warning(msg)


class ArtifactDatabaseEmptyError(RuntimeError):
    """圣遗物数据库为空异常"""

    _MESSAGE = "本地圣遗物数据库为空，请前往「设置」-> [同步] -> 圣遗物同步，手动同步。"

    def __init__(self) -> None:
        super().__init__(self._MESSAGE)
        log.warning(self._MESSAGE)


class ArtifactUpdateAvailableError(RuntimeError):
    """圣遗物有可用更新异常"""

    _MESSAGE = "检测到圣遗物最新数据更新，请前往「设置」-> [同步] -> 圣遗物同步，拉取最新数据。"

    def __init__(self) -> None:
        super().__init__(self._MESSAGE)
        log.warning(self._MESSAGE)


class LockIconNotFoundError(RuntimeError):
    """锁定/解锁图标定位失败异常"""

    _MESSAGE = "无法定位锁定/解锁图标，请确认游戏画面正常显示"

    def __init__(self) -> None:
        super().__init__(self._MESSAGE)
        log.warning(self._MESSAGE)
