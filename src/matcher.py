"""Carpool matching engine for McRoutePin (麦顺路).

The matcher decides whether two McDelivery (麦乐送) orders can share one
rider trip, which stop the rider should visit first, and how detour-ish
the combined route is.

Matching rule (三重匹配):
    1. 同一门店      — both orders are delivered by the same store
    2. 地理围栏      — partner lives within ``radius_km`` of the initiator
    3. 时间窗口      — partner joins within ``window_minutes``

Detour ratio (顺路度, order-insensitive):
    The rider must visit both destinations. Two visiting orders exist:

        route_A_first = d(store->A) + d(A->B)      # 先送发起人
        route_B_first = d(store->B) + d(B->A)      # 先送伙伴

    We pick the shorter route L (nearest-first, the classic 2-stop
    heuristic) and compare it against the longer *single* delivery the
    rider would have made anyway:

        r = L / max(d(store->A), d(store->B))

    r == 1.0   one stop is exactly on the way to the other — zero detour
    r >  2.5   the combined trip is 2.5x the unavoidable leg — decline

    This formulation is symmetric in A and B: swapping who is the
    initiator never changes the verdict (a property the naive
    "先送发起人" formula lacks).

The engine also powers the 拼单墙 (nearby ordering wall):
    :func:`rank_candidates` evaluates every open order on the wall and
    returns them sorted by detour ratio, so the user sees "who nearby is
    the most 顺路 to pool with".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .geo import encode_geohash, haversine_km
from .models import NearbyOrder, Party, PinSession, PinStatus, PinWall

#: Maximum detour ratio we accept. Above this the trip is a detour, not a carpool.
MAX_DETOUR_RATIO = 2.5

_TIERS = [
    # (upper bound of r, tier label, rider surcharge factor per unit of r-1)
    (1.3, "深度顺路", 0.10),
    (1.8, "中度顺路", 0.15),
    (MAX_DETOUR_RATIO, "轻度顺路", 0.20),
]


@dataclass
class MatchResult:
    ok: bool
    reason: str = ""
    detour_ratio: float = 0.0
    tier: str = ""
    route_km: float = 0.0
    delivery_order: str = ""      # 派单建议，如 "先送李四，再送张三"
    dist_store_to_initiator_km: float = 0.0
    dist_initiator_to_partner_km: float = 0.0
    dist_store_to_partner_km: float = 0.0


def leg_distances(session: PinSession) -> tuple[float, float, float]:
    """Return (store->initiator, initiator->partner, store->partner) in km."""
    s = session.store.as_tuple()
    a = session.initiator.destination.as_tuple()
    b = session.partner.destination.as_tuple()  # type: ignore[union-attr]
    return (
        haversine_km(*s, *a),
        haversine_km(*a, *b),
        haversine_km(*s, *b),
    )


def within_geofence(session: PinSession) -> bool:
    """Partner must live within ``radius_km`` of the initiator."""
    if session.partner is None:
        return False
    a = session.initiator.destination.as_tuple()
    b = session.partner.destination.as_tuple()
    return haversine_km(*a, *b) <= session.radius_km


def evaluate(session: PinSession, now: Optional[float] = None) -> MatchResult:
    """Run the full matching rule set against a session.

    On success the session is moved to ``MATCHED`` and ``detour_ratio``,
    ``route_km``, ``delivery_order`` and ``discount_tier`` are filled in
    for :func:`mcd_pindan.fee.split_fee`.
    """
    result = MatchResult(ok=False)

    if session.partner is None:
        result.reason = "尚无拼单伙伴加入"
        return result

    if not within_geofence(session):
        result.reason = (
            f"伙伴地址距发起人超过 {session.radius_km} 公里，超出拼单范围"
        )
        return result

    if session.is_expired(now):
        session.status = PinStatus.EXPIRED
        result.reason = "超过拼单时间窗口，已恢复原价"
        return result

    d_store_a, d_a_b, d_store_b = leg_distances(session)
    if max(d_store_a, d_store_b) < 1e-6:
        result.reason = "双方地址均与门店重合，无需外送拼单"
        return result

    name_a = session.initiator.display_name
    name_b = session.partner.display_name

    # Two visiting orders; pick the shorter (nearest-first heuristic).
    route_a_first = d_store_a + d_a_b   # 门店 -> 发起人 -> 伙伴
    route_b_first = d_store_b + d_a_b   # 门店 -> 伙伴 -> 发起人
    if route_a_first <= route_b_first:
        route, delivery_order = route_a_first, f"先送{name_a}，再送{name_b}"
    else:
        route, delivery_order = route_b_first, f"先送{name_b}，再送{name_a}"

    # Order-insensitive detour ratio: combined route vs the longer
    # single delivery the rider would have ridden anyway.
    ratio = route / max(d_store_a, d_store_b)

    result.detour_ratio = ratio
    result.route_km = route
    result.delivery_order = delivery_order
    result.dist_store_to_initiator_km = d_store_a
    result.dist_initiator_to_partner_km = d_a_b
    result.dist_store_to_partner_km = d_store_b

    if ratio > MAX_DETOUR_RATIO:
        result.reason = (
            f"绕路比 {ratio:.2f} 超过上限 {MAX_DETOUR_RATIO}，"
            "顺路程度不足，不建议拼单"
        )
        return result

    for upper, label, _ in _TIERS:
        if ratio <= upper:
            result.tier = label
            break

    result.ok = True
    session.status = PinStatus.MATCHED
    session.detour_ratio = ratio
    session.route_km = route
    session.delivery_order = delivery_order
    session.discount_tier = result.tier
    return result


def evaluate_candidate(
    wall: PinWall, candidate: NearbyOrder, now: Optional[float] = None
) -> MatchResult:
    """Evaluate one wall order as a potential partner for the initiator."""
    session = PinSession(
        store=wall.store,
        base_delivery_fee=wall.base_delivery_fee,
        initiator=wall.initiator,
        partner=Party(
            role="partner",
            display_name=candidate.display_name,
            destination=candidate.destination,
            order_amount=candidate.order_amount,
        ),
        radius_km=wall.radius_km,
        window_minutes=wall.window_minutes,
        created_at=wall.created_at,
    )
    session.status = PinStatus.WAITING_PARTNER
    return evaluate(session, now)


def rank_candidates(
    wall: PinWall, now: Optional[float] = None
) -> list[tuple[NearbyOrder, MatchResult]]:
    """拼单墙撮合：把墙上每个候选订单按顺路程度排序。

    Returns a list of ``(order, result)`` pairs sorted by detour ratio:
    matchable candidates first (best 顺路 on top), then rejects.
    Wall orders older than ``window_minutes`` are dropped beforehand.
    """
    wall.drop_expired(now)
    pairs = [(o, evaluate_candidate(wall, o, now)) for o in wall.candidates]
    pairs.sort(key=lambda p: (not p[1].ok, p[1].detour_ratio))
    return pairs


def geohash_bucket(wall: PinWall, precision: int = 6) -> str:
    """Coarse grid bucket of the initiator (used for wall pre-filtering)."""
    d = wall.initiator.destination
    return encode_geohash(d.lat, d.lon, precision)
