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

    _MESSAGE = "OCR 模型未下载，请前往「设置」页面点击「下载模型」"

    def __init__(self) -> None:
        super().__init__(self._MESSAGE)
        log.error(self._MESSAGE)
        from ui.gmessagebox import GMessageBox

        GMessageBox.error(self._MESSAGE)

class GameWindowNotFoundError(RuntimeError):
    """游戏窗口未找到异常。

    当截图模块无法定位原神窗口时抛出，调用方可选择：
    - 捕获后提示用户打开游戏
    - 捕获后重试
    - 向上传播由 QML UI 层展示错误
    """

    _MESSAGE = "未找到原神窗口，不要将游戏窗口最小化"

    def __init__(self) -> None:
        super().__init__(self._MESSAGE)
        log.warning(self._MESSAGE)
        from ui.gmessagebox import GMessageBox

        GMessageBox.warning(self._MESSAGE)