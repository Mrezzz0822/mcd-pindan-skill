"""Tests for the matching engine.

Key regression: the detour ratio must be order-insensitive. A partner
sitting exactly between the store and the initiator yields r == 1.0 no
matter which side is named "initiator".
"""

import unittest

from src.matcher import MAX_DETOUR_RATIO, evaluate, rank_candidates
from src.models import (
    GeoPoint,
    NearbyOrder,
    Party,
    PinSession,
    PinStatus,
    PinWall,
)

STORE = GeoPoint("门店", 39.98390, 116.31630)
# 三点共线：门店 --0.5km--> MID --0.4km--> FAR
MID = GeoPoint("丹棱街(必经之路上)", 39.98390, 116.310438)
FAR = GeoPoint("海淀大街(最远)", 39.98390, 116.305749)
# 门店反方向
OPPOSITE = GeoPoint("中关村大街(反方向)", 39.98390, 116.32600)


def make_session(partner_dest, radius_km=2.0, window_minutes=30):
    s = PinSession(
        store=STORE,
        base_delivery_fee=9.0,
        radius_km=radius_km,
        window_minutes=window_minutes,
        initiator=Party("initiator", "张三", FAR, 40.0),
        partner=Party("partner", "伙伴", partner_dest, 30.0),
    )
    s.status = PinStatus.WAITING_PARTNER
    return s


class TestEvaluate(unittest.TestCase):
    def test_collinear_partner_is_perfectly_on_the_way(self):
        """伙伴恰好在门店→发起人的必经之路上：绕路比应为 1.00。"""
        r = evaluate(make_session(MID))
        self.assertTrue(r.ok)
        self.assertAlmostEqual(r.detour_ratio, 1.00, places=2)
        self.assertEqual(r.tier, "深度顺路")

    def test_ratio_is_order_insensitive(self):
        """发起人与伙伴互换，结论不变（顺序无关性回归测试）。"""
        s1 = make_session(MID)
        s2 = PinSession(
            store=STORE,
            base_delivery_fee=9.0,
            initiator=Party("initiator", "伙伴", MID, 30.0),
            partner=Party("partner", "张三", FAR, 40.0),
        )
        s2.status = PinStatus.WAITING_PARTNER
        r1, r2 = evaluate(s1), evaluate(s2)
        self.assertTrue(r1.ok and r2.ok)
        self.assertAlmostEqual(r1.detour_ratio, r2.detour_ratio, places=6)

    def test_opposite_direction_is_rejected(self):
        r = evaluate(make_session(OPPOSITE))
        self.assertFalse(r.ok)
        self.assertGreater(r.detour_ratio, MAX_DETOUR_RATIO)

    def test_dispatch_suggestion_delivers_nearest_first(self):
        r = evaluate(make_session(MID))
        self.assertEqual(r.delivery_order, "先送伙伴，再送张三")
        self.assertAlmostEqual(r.route_km, 0.90, places=2)

    def test_out_of_geofence_rejected(self):
        far_away = GeoPoint("远郊", 40.05, 116.20)
        r = evaluate(make_session(far_away))
        self.assertFalse(r.ok)
        self.assertIn("超出拼单范围", r.reason)

    def test_expired_session_rejected(self):
        s = make_session(MID)
        r = evaluate(s, now=s.created_at + s.window_minutes * 60 + 1)
        self.assertFalse(r.ok)
        self.assertEqual(s.status, PinStatus.EXPIRED)

    def test_no_partner_rejected(self):
        s = PinSession(
            store=STORE,
            base_delivery_fee=9.0,
            initiator=Party("initiator", "张三", FAR, 40.0),
        )
        r = evaluate(s)
        self.assertFalse(r.ok)


class TestWall(unittest.TestCase):
    def setUp(self):
        self.wall = PinWall(
            store=STORE,
            base_delivery_fee=9.0,
            radius_km=2.0,
            window_minutes=30,
            initiator=Party("initiator", "张三", FAR, 42.5),
        )
        self.wall.add_orders([
            NearbyOrder("李四", GeoPoint("善缘街", 39.98430, 116.30460), 35.0),
            NearbyOrder("王五", OPPOSITE, 50.0),
            NearbyOrder("赵六", MID, 28.0),
        ])

    def test_best_candidate_ranks_first(self):
        ranked = rank_candidates(self.wall)
        self.assertEqual(ranked[0][0].display_name, "赵六")
        self.assertTrue(all(p[1].ok for p in ranked[:2]))
        self.assertFalse(ranked[2][1].ok)

    def test_expired_orders_dropped_from_wall(self):
        stale = NearbyOrder("老单", MID, 20.0)
        stale.created_at -= 31 * 60  # 31 分钟前上的墙
        self.wall.add(stale)
        ranked = rank_candidates(self.wall, now=self.wall.created_at + 31 * 60)
        names = [o.display_name for o, _ in ranked]
        self.assertNotIn("老单", names)


if __name__ == "__main__":
    unittest.main()
