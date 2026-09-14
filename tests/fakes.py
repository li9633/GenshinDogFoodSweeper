"""测试用的假端口
==============
遍历骨架（``SlotSweep`` / ``ListSweep``）只依赖契约里的端口，
所以可以用这些假实现覆盖整轮语义 —— 不需要截图、不需要点击、不需要游戏窗口。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.contracts.sweep import SweepTiming
from backend.models.artifact import ArtifactInfo, ArtifactStat
from backend.models.slot_models import ArtifactRarity, DetectResult, SlotObject

# 测试里不等待
FAST = SweepTiming(click_delay_s=0.0, detail_settle_s=0.0)


@dataclass
class FakeWorld:
    """模拟"真实列表"：格子内容取决于当前滚动到的页，而不是检测次数

    同时充当 ``SlotFinder`` 与 ``ListNavigator`` 两个端口。
    """

    pages: list[list[SlotObject]]
    current: int = 0
    to_top_calls: int = 0
    to_bottom_calls: int = 0
    next_page_calls: int = 0
    find_calls: int = 0

    def find(self, image: object) -> DetectResult:
        self.find_calls += 1
        return DetectResult(slots=list(self.pages[self.current]), bottom_y=0.0, debug_infos=())

    def to_top(self) -> None:
        self.to_top_calls += 1
        self.current = 0

    def to_bottom(self) -> None:
        self.to_bottom_calls += 1
        self.current = len(self.pages) - 1

    def next_page(self, det_result: object) -> bool:
        self.next_page_calls += 1
        if self.current + 1 >= len(self.pages):
            return False
        self.current += 1
        return True


@dataclass
class FakeScreen:
    """按脚本依次返回画面；用尽后重复最后一张"""

    frames: list[object]
    calls: int = 0
    prepared: int = 0

    def prepare(self) -> None:
        self.prepared += 1

    def capture(self) -> object | None:
        index = min(self.calls, len(self.frames) - 1)
        self.calls += 1
        return self.frames[index]


@dataclass
class FakePointer:
    clicks: list[tuple[int, int]] = field(default_factory=list)

    def click(self, x: int, y: int) -> None:
        self.clicks.append((x, y))


@dataclass
class FakeReader:
    """按识别次数依次返回结果；None 表示识别失败"""

    results: list[ArtifactInfo | None]
    calls: int = 0

    def read(self, image: object) -> ArtifactInfo | None:
        index = min(self.calls, len(self.results) - 1)
        self.calls += 1
        return self.results[index]


@dataclass
class FakeToggler:
    toggles: list[object] = field(default_factory=list)

    def toggle(self, image: object) -> None:
        self.toggles.append(image)


def make_frame(fill: int = 200) -> object:
    """一张"非空格子"的假截图

    尺寸要足够大，否则 ``AnchorLocator.is_empty_slot`` 会因为采样区越界而判为空格子。
    """
    import numpy as np

    return np.full((400, 400, 3), fill, dtype=np.uint8)


def make_slot(
    index: int,
    *,
    rarity: ArtifactRarity = ArtifactRarity.FIVE,
    locked: bool = False,
) -> SlotObject:
    return SlotObject(
        cx=100 + index * 10,
        cy=200,
        x=0,
        y=0,
        w=10,
        h=10,
        rarity=rarity,
        locked=locked,
        row=0,
        col=index,
    )


def make_artifact(
    *,
    rarity: int = 5,
    main_stat: str = "生命值",
    set_name: str = "角斗士的终幕礼",
    piece_type: str = "生之花",
    sub_values: tuple[float, ...] = (),
) -> ArtifactInfo:
    """构建一件可区分的圣遗物（主词条/副词条不同 → 去重判定视为不同件）"""
    from backend.models.artifact import SubStat

    return ArtifactInfo(
        set_name=set_name,
        piece_type=piece_type,
        rarity=rarity,
        main_stat=ArtifactStat(name=main_stat, value=4780.0, is_percentage=False),
        sub_stats=[
            SubStat(name=f"词条{i}", value=value, is_percentage=True, is_activated=True)
            for i, value in enumerate(sub_values)
        ],
    )
