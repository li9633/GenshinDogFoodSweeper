"""圣遗物识别策略 — 按需识别指定字段，避免全量 OCR 耗时"""

from __future__ import annotations

from enum import Enum, auto


class ArtifactRecognitionField(Enum):
    """可独立识别的圣遗物字段。

    BBS 匹配分为两步：
    - SET_NAME：快速验证圣遗物是否存在于数据库（模糊匹配名称）
    - SET_EFFECTS：查询套装效果等完整信息（额外 DB 查询，耗时较高）

    用法：
        # 全局策略 — 全部识别
        ArtifactRecognizer.STRATEGY = frozenset({ArtifactRecognitionField.ALL})

        # 只验证名称（最快，跳过套装效果查询）
        ArtifactRecognizer.STRATEGY = frozenset({ArtifactRecognitionField.SET_NAME})

        # 验证名称 + 套装效果（完整匹配）
        ArtifactRecognizer.STRATEGY = frozenset({
            ArtifactRecognitionField.SET_NAME,
            ArtifactRecognitionField.SET_EFFECTS,
        })

        # 名称 + 主词条 + 等级
        ArtifactRecognizer.STRATEGY = frozenset({
            ArtifactRecognitionField.SET_NAME,
            ArtifactRecognitionField.MAIN_STAT,
            ArtifactRecognitionField.LEVEL,
        })
    """

    ALL = auto()          # 全部识别
    SET_NAME = auto()     # 套装名（OCR 圣遗物名称 + BBS 模糊匹配验证）
    SET_EFFECTS = auto()  # 套装效果查询（依赖 SET_NAME，额外 DB 查询）
    PIECE_TYPE = auto()   # 部位（OCR 部位+主词条 + BBS 匹配）
    MAIN_STAT = auto()    # 主词条（OCR 部位+主词条 + 解析）
    SUB_STATS = auto()    # 副词条（OCR 副词条区 + 解析）
    LEVEL = auto()        # 等级（OCR 圣遗物等级 + 解析）
    RARITY = auto()       # 星级（颜色检测）
    LOCK_STATUS = auto()  # 锁定状态（模板匹配）