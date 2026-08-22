"""狗粮清理规则数据模型"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class SubStatCondition:
    """副词条匹配条件：名称 + 可选值比较"""

    name: str = ""
    op: str = ""  # "", ">", "<", ">=", "<=", "="
    value: float = 0.0

    def to_dict(self) -> dict:
        d: dict = {"name": self.name}
        if self.op:
            d["op"] = self.op
            d["value"] = self.value
        return d

    @classmethod
    def from_dict(cls, d: dict) -> SubStatCondition:
        return cls(
            name=d.get("name", ""),
            op=d.get("op", ""),
            value=d.get("value", 0.0),
        )


@dataclass
class DogfoodRule:
    """单条狗粮清理规则

    name 为唯一标识，通配符 * 匹配任意值，空字符串不参与匹配。
    """

    name: str = ""
    part: str = "*"  # 部位白名单
    part_exclude: str = ""  # 部位黑名单
    main_stat: str = "*"  # 主词条
    set_name: str = "*"  # 套装名
    sub_stats: list[SubStatCondition] = field(default_factory=list)
    sub_count: int = 0
    action: str = "keep"  # "keep" / "discard"
    priority: int = 0
    enabled: bool = True
    include_unactivated: bool = True  # 副词条匹配时是否考虑待激活词条
    include_main_stat: bool = False  # 主词条也计入副词条匹配数

    def to_dict(self) -> dict:
        d = asdict(self)
        d["sub_stats"] = [s.to_dict() for s in self.sub_stats]
        return d

    @classmethod
    def from_dict(cls, d: dict) -> DogfoodRule:
        subs = d.get("sub_stats", [])
        parsed: list[SubStatCondition] = []
        for s in subs:
            parsed.append(SubStatCondition.from_dict(s))
        d = {**d, "sub_stats": parsed}
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})