"""自动化层异常"""

# import 即安装全局异常处理器（类似 Spring Boot @ControllerAdvice）
from backend.exceptions.automation import exception_handler  # noqa: F401
from backend.exceptions.automation.exceptions import (
    GameWindowNotFoundError,
    OcrModelNotReadyError,
)

__all__ = ["GameWindowNotFoundError", "OcrModelNotReadyError"]