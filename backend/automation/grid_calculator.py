"""
网格坐标计算器 — 纯逻辑层，无 Qt 依赖
=====================================
根据行列参数计算圣遗物背包网格中每个格子的中心坐标。
所有方法均为静态方法，可在任意线程中安全调用。
"""

from __future__ import annotations

from collections.abc import Iterator


class GridCalculator:
    """网格坐标计算器 — 纯函数，无状态，无 Qt 依赖"""

    @staticmethod
    def cell_center(
        margin_x: int,
        margin_y: int,
        item_w: int,
        item_h: int,
        gap: int,
        row: int,
        col: int,
    ) -> tuple[int, int]:
        """计算指定行列格子的中心坐标（窗口相对坐标）。

        Args:
            margin_x/y: 网格区域左上角偏移
            item_w/h: 每个格子的宽高
            gap: 格子间距
            row/col: 行号和列号（从0开始）

        Returns:
            (cx, cy) 窗口相对坐标
        """
        cx = margin_x + (gap + item_w) * col + item_w // 2
        cy = margin_y + (gap + item_h) * row + item_h // 2
        return (cx, cy)

    @staticmethod
    def cell_center_absolute(
        margin_x: int,
        margin_y: int,
        item_w: int,
        item_h: int,
        gap: int,
        row: int,
        col: int,
        origin_x: int,
        origin_y: int,
    ) -> tuple[int, int]:
        """计算指定行列格子的中心坐标（屏幕绝对坐标）。

        Args:
            margin_x/y: 网格区域左上角偏移
            item_w/h: 每个格子的宽高
            gap: 格子间距
            row/col: 行号和列号（从0开始）
            origin_x/y: 窗口左上角屏幕坐标

        Returns:
            (ax, ay) 屏幕绝对坐标
        """
        cx, cy = GridCalculator.cell_center(
            margin_x, margin_y, item_w, item_h, gap, row, col
        )
        return (origin_x + cx, origin_y + cy)

    @staticmethod
    def iter_cells(
        rows: int,
        cols: int,
        margin_x: int,
        margin_y: int,
        item_w: int,
        item_h: int,
        gap: int,
        origin_x: int = 0,
        origin_y: int = 0,
    ) -> Iterator[tuple[int, int, int, int]]:
        """按行优先顺序遍历所有格子中心坐标。

        Yields:
            (row, col, x, y) 其中 x, y 为屏幕绝对坐标
        """
        for row in range(rows):
            for col in range(cols):
                x, y = GridCalculator.cell_center_absolute(
                    margin_x, margin_y, item_w, item_h, gap,
                    row, col, origin_x, origin_y,
                )
                yield (row, col, x, y)