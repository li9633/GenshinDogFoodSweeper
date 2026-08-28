"""自动化层异常定义"""

from utils.logger import log


class OcrModelNotReadyError(RuntimeError):
    """OCR 模型未就绪异常。

    构造时自动完成：
      1. log.error 记录日志
      2. GMessageBox 弹窗提示用户

    调用方只需 raise OcrModelNotReadyError() 即可，无需手动处理日志和弹窗。
    Signal 跨线程安全：即使从后台线程抛出，GMessageBox 弹窗也会自动投递到主线程。
    """

    _MESSAGE = "OCR 模型未下载，请前往「设置」-> [模型] -> 点击「下载模型」"

    def __init__(self) -> None:
        super().__init__(self._MESSAGE)
        log.error(self._MESSAGE)
        from ui.gmessagebox import GMessageBox

        GMessageBox.error(self._MESSAGE)

# 窗口未找到的两种场景消息（screen_capture 判断场景，exception_handler 过滤 QML 日志）
WINDOW_NOT_FOUND_PROCESS_MSG = "请先启动原神游戏"
WINDOW_NOT_FOUND_MINIMIZED_MSG = "请将原神窗口置于前台"


class GameWindowNotFoundError(RuntimeError):
    """游戏窗口未找到异常。

    由调用方（screen_capture / window_helper）根据进程状态传入对应消息：
    - WINDOW_NOT_FOUND_PROCESS_MSG    → 进程未启动
    - WINDOW_NOT_FOUND_MINIMIZED_MSG  → 窗口不可见

    构造时自动完成 log + GMessageBox 弹窗，调用方无需额外处理。
    """

    _MESSAGE = WINDOW_NOT_FOUND_PROCESS_MSG  # 用于 exception_handler 匹配

    def __init__(self, message: str = "") -> None:
        msg = message or self._MESSAGE
        super().__init__(msg)
        log.warning(msg)
        from ui.gmessagebox import GMessageBox

        GMessageBox.warning(msg)



class ArtifactDatabaseEmptyError(RuntimeError):
    """圣遗物数据库为空异常。

    仅作为消息载体，不在构造时自动弹窗（由调用方决定 UI 展示方式）。
    """

    _MESSAGE = "本地圣遗物数据库为空，请前往「设置」-> [同步] -> 圣遗物同步，手动同步。"

    def __init__(self) -> None:
        super().__init__(self._MESSAGE)


class ArtifactUpdateAvailableError(RuntimeError):
    """圣遗物有可用更新异常。

    仅作为消息载体，不在构造时自动弹窗（由调用方决定 UI 展示方式）。
    """

    _MESSAGE = "检测到圣遗物最新数据更新，请前往「设置」-> [同步] -> 圣遗物同步，拉取最新数据。"

    def __init__(self) -> None:
        super().__init__(self._MESSAGE)