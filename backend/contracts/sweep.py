"""逐格遍历契约
==============
「定位列表 → 逐格点击 → 读出详情 → 判定 → 动作 → 翻页」这套骨架被
圣遗物扫描器 / 锁定器 / 清理器（以及调试面板）共用，这里定义它依赖的**端口**
与**策略**接口；具体实现见 ``backend/automation/sweep*.py``。

端口全部是 Protocol：底层原语（截图 / 鼠标 / 格子检测 / 识别 / 滚动）由适配器接上，
其中 ``SlotDetector`` / ``PageScroller`` / ``SliderScroller`` 属冻结模块，只调用不改。

契约只依赖 ``backend/models``：不得反向依赖 automation / features / ui。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, ClassVar, Protocol, runtime_checkable

from backend.models.artifact import ArtifactInfo
from backend.models.slot_models import SlotObject


@dataclass(frozen=True)
class SweepTiming:
    """遍历时序参数（集中一处，便于按机器/画质调档）"""

    click_delay_s: float = 0.35  # 点击格子后等待
    detail_settle_s: float = 0.15  # 点击后等待详情面板刷新
    tick_delay_ms: int = 30  # 翻页拖动滑块的步进间隔
    page_settle_ms: int = 200  # 翻页后等待列表稳定


@dataclass(frozen=True)
class SlotContext:
    """单个格子的遍历上下文（交给策略做判定与动作）"""

    page: int  # 0-based 页码
    index: int  # 本页第几个（1-based）
    total: int  # 本页格子总数
    slot: SlotObject
    image: Any  # 详情面板截图（识别用的那张）
    reread: Callable[[], ArtifactInfo | None] | None = None
    """重新截屏并识别当前格子（详情面板未刷新时的重试入口）；不支持时为 None"""


@runtime_checkable
class ScreenSource(Protocol):
    """画面来源：聚焦游戏窗口并截图"""

    def prepare(self) -> None:
        """聚焦游戏窗口 + 注入坐标原点（每次遍历开始前调用一次）"""
        ...

    def capture(self) -> Any | None:
        """截取当前游戏画面；失败返回 None"""
        ...


@runtime_checkable
class Pointer(Protocol):
    """指针操作"""

    def click(self, x: int, y: int) -> None:
        """在窗口相对坐标 (x, y) 处点击"""
        ...


@runtime_checkable
class SlotFinder(Protocol):
    """格子检测（冻结实现 ``SlotDetector`` 的适配口）"""

    def find(self, image: Any) -> Any:
        """返回 ``DetectResult``（``.slots`` 为空表示该页没有格子）"""
        ...


@runtime_checkable
class ArtifactReader(Protocol):
    """详情识别：把详情面板截图读成 ``ArtifactInfo``"""

    def read(self, image: Any) -> ArtifactInfo | None:
        """识别失败返回 None（不应抛异常中断整轮遍历）"""
        ...


@runtime_checkable
class ListNavigator(Protocol):
    """列表导航：回到顶部 / 滚到底部 / 翻到下一页"""

    def to_top(self) -> None:
        """把列表滚到顶部"""
        ...

    def to_bottom(self) -> None:
        """把列表滚到底部（锚点定位流程需要）；失败时应抛异常由调用方处理"""
        ...

    def next_page(self, det_result: Any) -> bool:
        """按当前页的检测结果翻页；返回 False 表示已是最后一页"""
        ...


@runtime_checkable
class SweepPolicy(Protocol):
    """遍历策略：三个功能唯一的差异点（预筛 / 判定 / 动作）

    默认实现见 ``backend/automation/sweep.py`` 的 ``BaseSweepPolicy``：
    全部进、全部识别、识别后继续。
    """

    def should_click(self, slot: SlotObject) -> bool:
        """点击前的格子预筛（False = 跳过该格，省一次点击与识别）"""
        ...

    def needs_detail(self) -> bool:
        """点击后是否需要「截图 + 识别详情」

        返回 False = **纯点击模式**：点完直接进下一格，不截图、不识别
        （调试面板的批量点击、只做点击的批量操作都走这条路径）。
        """
        ...

    def should_read(self, slot: SlotObject, image: Any) -> bool:
        """点击并截图后、识别前的检查（False = 不识别，例如空格子）"""
        ...

    def on_artifact(self, artifact: ArtifactInfo, ctx: SlotContext) -> bool:
        """识别成功后的判定与动作；返回 False 表示结束整轮遍历"""
        ...


@dataclass(frozen=True)
class SweepSummary:
    """一次列表遍历的结果统计"""

    pages_scanned: int
    slots_entered: int
    artifacts_read: int
    stopped_reason: str  # "completed" | "user_stop" | "policy_stop" | "page_limit"

    COMPLETED: ClassVar[str] = "completed"
    USER_STOP: ClassVar[str] = "user_stop"
    POLICY_STOP: ClassVar[str] = "policy_stop"
    PAGE_LIMIT: ClassVar[str] = "page_limit"
