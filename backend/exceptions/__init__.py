"""异常定义 — 按领域分层

automation/ — 自动化层异常（OCR、窗口检测、热键等）
api/        — FastAPI 层异常（将来）
"""

from backend.exceptions.automation import GameWindowNotFoundError, OcrModelNotReadyError

__all__ = ["GameWindowNotFoundError", "OcrModelNotReadyError"]