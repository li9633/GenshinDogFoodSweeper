"""
网格点击配置 — 纯数据类，无任何依赖
===================================
定义网格点击所需的全部参数，供 BatchClickWorker 和 FullScanWorker 共用。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GridClickConfig:
    """网格点击配置

    所有坐标均为窗口相对坐标（origin_x/y 除外）。
    """

    origin_x: int = 0
    origin_y: int = 0
    margin_x: int = 0
    margin_y: int = 0
    item_w: int = 0
    item_h: int = 0
    gap: int = 0
    rows: int = 4
    cols: int = 8
    interval_ms: int = 100
    auto_focus: bool = False