"""圣遗物识别策略 — 按需识别指定字段，避免全量 OCR 耗时"""

from __future__ import annotations

from enum import Enum, auto


class ArtifactRecognitionField(Enum):
    """可独立识别的圣遗物字段。

    SET_NAME 快速验证圣遗物是否存在于数据库（模糊匹配名称），
    SET_EFFECTS 查询套装效果等完整信息（额外 DB 查询，耗时较高）。
    """

    ALL = auto()          # 全部识别
    SET_NAME = auto()     # 套装名（OCR + 模糊匹配验证）
    SET_EFFECTS = auto()  # 套装效果查询（依赖 SET_NAME，额外 DB 查询）
    PIECE_TYPE = auto()   # 部位（OCR 部位+主词条 + 匹配）
    MAIN_STAT = auto()    # 主词条（OCR + 解析）
    SUB_STATS = auto()    # 副词条（OCR + 解析）
    LEVEL = auto()        # 等级（OCR + 解析）
    RARITY = auto()       # 星级（颜色检测）
    LOCK_STATUS = auto()  # 锁定状态（模板匹配）