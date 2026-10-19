"""McRoutePin (麦顺路) end-to-end demo.

Runs a full 拼单墙 (nearby ordering wall) scenario with no MCP token
required:

    1. 张三在「中关村门店」想点麦乐送，配送费 ¥9，打开拼单墙
    2. 墙上有 3 个附近正在点单的人：李四（同方向）、王五（反方向）、
       赵六（恰好住在门店到张三的必经之路上）
    3. 引擎对每个候选计算顺路度并排序（PDD 式：谁顺路拼谁）
    4. 最顺路的赵六与张三成团，双方各省 50% 配送费
    5. 生成含派单建议（先送谁）的拼单卡片

Usage:
    python demo.py
"""

from __future__ import annotations

from src.fee import render_share_card, split_fee
from src.matcher import geohash_bucket, rank_candidates
from src.models import GeoPoint, NearbyOrder, Party, PinWall


def banner(title: str) -> None:
    print()
    print("=" * 56)
    print(f"  {title}")
    print("=" * 56)


def main() -> None:
    store = GeoPoint(name="麦当劳(北京中关村大街餐厅)", lat=39.98390, lon=116.31630)
    base_fee = 9.0  # 由 calculate-price 实际返回，此处用常见麦乐送配送费

    banner("场景：张三打开拼单墙（麦乐送 ¥9 配送费）")
    wall = PinWall(
        store=store,
        base_delivery_fee=base_fee,
        radius_km=2.0,
        window_minutes=30,
        initiator=Party(
            role="initiator",
            display_name="张三",
            destination=GeoPoint(
                name="海淀大街3号 互联网金融中心", lat=39.98390, lon=116.305749
            ),
            order_amount=42.5,
        ),
    )
    print(f"门店: {wall.store.name}")
    print(f"发起人: {wall.initiator.display_name} → {wall.initiator.destination.name}")
    print(f"单人配送费: ¥{base_fee}，拼单窗口: {wall.window_minutes} 分钟")
    print(f"发起人所在 geohash 网格: {geohash_bucket(wall)}")

    banner("拼单墙：附近正在点单的 3 位用户")
    wall.add_orders([
        NearbyOrder(
            display_name="李四",
            destination=GeoPoint(name="善缘街1号 立方庭", lat=39.98430, lon=116.30460),
            order_amount=35.0,
        ),
        NearbyOrder(
            display_name="王五",
            destination=GeoPoint(
                name="中关村大街27号 中关村大厦", lat=39.98390, lon=116.32600
            ),
            order_amount=50.0,
        ),
        NearbyOrder(
            display_name="赵六",
            destination=GeoPoint(name="丹棱街 甲1号", lat=39.98390, lon=116.310438),
            order_amount=28.0,
        ),
    ])
    for o in wall.candidates:
        print(f"  🧍 {o.display_name} @ {o.destination.name}（餐品 ¥{o.order_amount}）")

    banner("撮合引擎：按顺路程度为每位候选打分排序")
    ranked = rank_candidates(wall)
    for order, result in ranked:
        if result.ok:
            print(
                f"  ✅ {order.display_name}: 绕路比 {result.detour_ratio:.2f}"
                f" → {result.tier}，一趟总里程 {result.route_km:.2f} km"
            )
        else:
            print(f"  ❌ {order.display_name}: {result.reason}")

    banner("成团：张三 × 最顺路的伙伴")
    best_order, best_result = ranked[0]
    print(f"最优伙伴: {best_order.display_name}（绕路比 {best_result.detour_ratio:.2f}）")

    # 用最优候选建立正式拼单会话
    from src.matcher import evaluate
    from src.models import PinSession, PinStatus

    session = PinSession(
        store=store,
        base_delivery_fee=base_fee,
        radius_km=wall.radius_km,
        window_minutes=wall.window_minutes,
        initiator=wall.initiator,
        partner=Party(
            role="partner",
            display_name=best_order.display_name,
            destination=best_order.destination,
            order_amount=best_order.order_amount,
        ),
    )
    session.status = PinStatus.WAITING_PARTNER
    result = evaluate(session)
    print(f"匹配结果: {'✅ 成功' if result.ok else '❌ ' + result.reason}")
    print(
        f"三段距离: 门店→{wall.initiator.display_name} "
        f"{result.dist_store_to_initiator_km:.2f} km, "
        f"{wall.initiator.display_name}→{best_order.display_name} "
        f"{result.dist_initiator_to_partner_km:.2f} km, "
        f"门店→{best_order.display_name} {result.dist_store_to_partner_km:.2f} km"
    )
    print()
    split = split_fee(session)
    print(render_share_card(session, split))

    banner("Demo 结束")
    print("真实环境中：确认后双方各自调用 create-order 下单（同一门店），")
    print("派单建议随订单备注提交；query-order 同步配送进度。")
    print("在线可视化演示见 demo/index.html（无需任何 Token）。")


if __name__ == "__main__":
    main()
