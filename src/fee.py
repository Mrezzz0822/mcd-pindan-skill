"""Delivery-fee pooling and split for McRoutePin (麦顺路).

Pricing model
-------------
A single McDelivery order pays the full delivery fee ``F`` (returned by
the ``calculate-price`` MCP tool); two separate orders cost the customer
side ``2F`` in total while the rider drives two trips. When two orders
share one rider trip, the rider's extra cost is only the detour segment,
so the platform can collect a pooled fee smaller than ``2F`` but larger
than ``F`` — customers pay less *and* the platform earns more per trip::

    F_pool = F * (1 + k * (r - 1))          # k = 顺路档位系数, r = 绕路比
    F_pool is always in [F, 1.3F]  for r <= 2.5, so:

    customer-side savings = 2F - F_pool  >= 0.7F  (both trips combined)

Split rule — 对称均摊 (symmetric, game-theoretically sound):
    Both parties are equally necessary for the pool to form (drop either
    one and the discount vanishes), so their marginal contributions are
    identical and the Shapley value of this 2-player game is a 50/50
    split of the savings::

        fee_each = F - (2F - F_pool) / 2

    Consequences (all guaranteed by construction, not by a patch-up
    check):

    1. Neither side ever pays more than the single-order fee ``F``.
    2. Both sides always save the same amount, 35%–50% of ``F`` each
       for r in [1, 2.5] — no "initiator's penalty", so users are never
       incentivised to wait for somebody else to start the pool.
    3. The savings are real for the *merged-trip* scenario the skill
       proposes; see README "结算边界" for how settlement works today.
"""

from __future__ import annotations

from dataclasses import dataclass

from .matcher import _TIERS, leg_distances
from .models import PinSession, PinStatus


@dataclass
class FeeSplit:
    pooled_fee: float          # 合并行程平台计收的配送费（一趟）
    standalone_total: float    # 双方各自下单的配送费合计（两趟）
    initiator_fee: float       # 发起人分摊的配送费
    partner_fee: float         # 伙伴分摊的配送费
    initiator_saving: float    # 发起人相对单人下单节省的金额
    partner_saving: float      # 伙伴相对单人下单节省的金额
    initiator_saving_pct: float
    partner_saving_pct: float
    platform_gain: float       # 平台单趟多收（相对单独送发起人一单）


def _surcharge_factor(tier: str) -> float:
    for _, label, factor in _TIERS:
        if label == tier:
            return factor
    return 0.20


def split_fee(session: PinSession) -> FeeSplit:
    """Split the pooled delivery fee between both parties.

    Precondition: ``session`` has been successfully matched (status
    ``MATCHED``) so ``detour_ratio`` and ``discount_tier`` are filled in.
    """
    if session.status != PinStatus.MATCHED:
        raise ValueError("拼单尚未匹配成功，无法计算分摊")

    f = session.base_delivery_fee
    r = session.detour_ratio
    factor = _surcharge_factor(session.discount_tier)
    pooled = round(f * (1 + factor * (r - 1)), 2)
    standalone_total = round(2 * f, 2)

    # 对称均摊：省下的钱五五分，双方等额受益（Shapley 值）。
    saving_total = round(standalone_total - pooled, 2)
    half = round(saving_total / 2, 2)
    fee_a = round(f - half, 2)
    fee_b = round(pooled - fee_a, 2)

    split = FeeSplit(
        pooled_fee=pooled,
        standalone_total=standalone_total,
        initiator_fee=fee_a,
        partner_fee=fee_b,
        initiator_saving=round(f - fee_a, 2),
        partner_saving=round(f - fee_b, 2),
        initiator_saving_pct=round((f - fee_a) / f * 100, 1),
        partner_saving_pct=round((f - fee_b) / f * 100, 1),
        platform_gain=round(pooled - f, 2),
    )
    session.pooled_fee = split.pooled_fee
    session.initiator_fee = split.initiator_fee
    session.partner_fee = split.partner_fee
    return split


def render_share_card(session: PinSession, split: FeeSplit) -> str:
    """Render the shareable 拼单卡片 shown to both parties."""
    assert session.partner is not None
    f = session.base_delivery_fee
    lines = [
        "🍔 麦顺路 · 拼单卡片",
        f"拼单号: {session.session_id}",
        f"门店: {session.store.name}",
        f"时间窗: 剩 {int(session.remaining_seconds() // 60)} 分钟",
        "",
        f"🧍 {session.initiator.display_name}（发起人）",
        f"   地址: {session.initiator.destination.name}",
        f"   配送费: ¥{f} → ¥{split.initiator_fee}（省 {split.initiator_saving_pct}%）",
        f"🧍 {session.partner.display_name}（伙伴）",
        f"   地址: {session.partner.destination.name}",
        f"   配送费: ¥{f} → ¥{split.partner_fee}（省 {split.partner_saving_pct}%）",
        "",
        f"顺路度: {session.detour_ratio:.2f}（{session.discount_tier}）",
        f"骑手一趟总里程: {session.route_km:.2f} km",
        f"派单建议: {session.delivery_order}",
        f"配送费合计: ¥{split.pooled_fee}（各自下单为 ¥{split.standalone_total}）",
    ]
    return "\n".join(lines)
