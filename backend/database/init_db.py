"""
数据库初始化
============
创建所有表。
"""

from .repository.artifact_piece_repo import ArtifactPieceRepo
from .repository.artifact_set_repo import ArtifactSetRepo
from .repository.dogfood_rule_repo import DogfoodRuleRepo
from .repository.log_repo import LogRepo
from .repository.settings_repo import SettingsRepo


def create_tables() -> None:
    """创建所有数据库表（幂等）。"""
    ArtifactSetRepo.create_table()
    ArtifactPieceRepo.create_table()
    DogfoodRuleRepo.create_table()
    SettingsRepo.create_table()
    LogRepo.create_table()