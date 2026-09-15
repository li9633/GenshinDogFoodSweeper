"""自动化层异常

注意：本包**不再在导入时安装全局异常过滤器**（那会让一次 `from ... import` 悄悄改变
全局行为）。需要过滤器时由入口显式调用
``backend.exceptions.automation.exception_handler.install_exception_filters()``。
"""

from backend.exceptions.automation.exceptions import (
    ArtifactDatabaseEmptyError,
    ArtifactUpdateAvailableError,
    GameWindowNotFoundError,
    LockIconNotFoundError,
    OcrModelNotReadyError,
)

__all__ = [
    "ArtifactDatabaseEmptyError",
    "ArtifactUpdateAvailableError",
    "GameWindowNotFoundError",
    "LockIconNotFoundError",
    "OcrModelNotReadyError",
]
