"""Data models for McRoutePin (麦顺路) delivery carpool sessions.

Two cooperating objects:

- :class:`PinWall` — 拼单墙. Simulates the "nearby ordering wall" that a
  store exposes: open McDelivery orders from the same store, visible to
  users who consider pooling.
- :class:`PinSession` — a two-party carpool session negotiated from the
  wall, including the fair fee split and the rider dispatch suggestion.

Real-world data sources (see MCP_INTEGRATION.md):
    store / addresses      -> McDonald's MCP tools (names, fees)
    precise coordinates    -> user-provided (long-press on any map app),
                              because the MCP has no geocoding tool
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class PinStatus(str, Enum):
    """State machine of a carpool (拼单) session."""

    CREATED = "CREATED"                  # 发起人已创建拼单，等待伙伴加入
    WAITING_PARTNER = "WAITING_PARTNER"  # 拼单卡片已生成，等待伙伴确认
    MATCHED = "MATCHED"                  # 双方地址匹配成功，展示优惠方案
    CONFIRMED = "CONFIRMED"              # 双方均确认，可以分别下单
    ORDERED = "ORDERED"                  # 双方订单均已创建
    EXPIRED = "EXPIRED"                  # 超过时间窗口未拼成，恢复原价
    CANCELLED = "CANCELLED"              # 任一方取消


@dataclass
class GeoPoint:
    """A named location on the map."""

    name: str
    lat: float
    lon: float

    def as_tuple(self) -> tuple[float, float]:
        return (self.lat, self.lon)


@dataclass
class Party:
    """One side of a carpool: the order owner and delivery destination."""

    role: str                     # "initiator" | "partner"
    display_name: str
    destination: GeoPoint
    order_amount: float           # 餐品金额（不含配送费），单位：元


@dataclass
class NearbyOrder:
    """An open order visible on the 拼单墙 (nearby ordering wall)."""

    display_name: str
    destination: GeoPoint
    order_amount: float
    order_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    created_at: float = field(default_factory=time.time)


@dataclass
class PinSession:
    """A carpool session between two parties ordering from the same store."""

    store: GeoPoint
    base_delivery_fee: float      # 麦乐送单人配送费，来自 calculate-price
    initiator: Party
    partner: Optional[Party] = None
    radius_km: float = 2.0        # 拼单双方围栏：双方直线距离上限
    window_minutes: int = 30      # 拼单有效时间窗口（分钟）
    status: PinStatus = PinStatus.CREATED
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0.0
    detour_ratio: float = 0.0     # 绕路比 r（双向取优后）
    discount_tier: str = ""
    route_km: float = 0.0         # 合并配送总里程（先送近者、再送远者）
    delivery_order: str = ""      # 派单建议："先送张三，再送李四"
    pooled_fee: float = 0.0
    initiator_fee: float = 0.0
    partner_fee: float = 0.0

    def __post_init__(self) -> None:
        if not self.expires_at:
            self.expires_at = self.created_at + self.window_minutes * 60

    def remaining_seconds(self, now: Optional[float] = None) -> float:
        now = time.time() if now is None else now
        return max(0.0, self.expires_at - now)

    def is_expired(self, now: Optional[float] = None) -> bool:
        return self.remaining_seconds(now) <= 0


@dataclass
class PinWall:
    """拼单墙：同一门店下、正在等待拼单的公开订单列表。

    现实映射：麦乐送为麦当劳自配送，平台侧完全掌握同一门店的实时
    订单流；本结构即「把附近正在点单的人亮出来」这一产品提案的最小
    数据模型。候选订单按 geohash 网格粗筛，只在同网格/邻网格内做
    精确匹配，与真实系统的空间索引做法一致。
    """

    store: GeoPoint
    base_delivery_fee: float
    initiator: Party
    candidates: list[NearbyOrder] = field(default_factory=list)
    radius_km: float = 2.0
    window_minutes: int = 30
    wall_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    created_at: float = field(default_factory=time.time)

    def add(self, order: NearbyOrder) -> None:
        self.candidates.append(order)

    def add_orders(self, orders: list[NearbyOrder]) -> None:
        self.candidates.extend(orders)

    def drop_expired(self, now: Optional[float] = None) -> None:
        """Remove wall orders older than the pooling window."""
        now = time.time() if now is None else now
        self.candidates = [
            o for o in self.candidates if now - o.created_at <= self.window_minutes * 60
        ]
