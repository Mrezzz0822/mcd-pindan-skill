"""Tests for fee pooling and the symmetric split.

The split guarantees (all by construction):
    1. nobody pays more than the single-order fee F
    2. both parties save equally, and savings stay within [35%, 50%] of F
       for every accepted detour ratio (r <= 2.5)
    3. the platform's per-trip take F_pool stays within [F, 1.3F]
"""

import unittest

from src.fee import split_fee
from src.matcher import MAX_DETOUR_RATIO, evaluate
from src.models import GeoPoint, Party, PinSession, PinStatus

STORE = GeoPoint("门店", 39.98390, 116.31630)
F = 9.0


def matched_session(store_dest_pair):
    """Build a MATCHED session from an (initiator, partner) point pair."""
    a, b = store_dest_pair
    s = PinSession(
        store=STORE,
        base_delivery_fee=F,
        initiator=Party("initiator", "张三", a, 40.0),
        partner=Party("partner", "李四", b, 30.0),
    )
    s.status = PinStatus.WAITING_PARTNER
    result = evaluate(s)
    assert result.ok, result.reason
    return s, result


def _grid_of_geometries():
    """Collinear / perpendicular / angled geometries spanning r in [1, 2.4]."""
    cases = []
    # 伙伴在门店→发起人的中途（r = 1.0）
    cases.append((
        GeoPoint("A", 39.98390, 116.305749),
        GeoPoint("B", 39.98390, 116.310438),
    ))
    # 伙伴与发起人同距门店、相隔一段（中度顺路）
    cases.append((
        GeoPoint("A", 39.98390, 116.305749),
        GeoPoint("B", 39.99000, 116.305749),
    ))
    # 伙伴明显偏向一侧（轻度顺路）
    cases.append((
        GeoPoint("A", 39.98390, 116.305749),
        GeoPoint("B", 39.98390, 116.31350),
    ))
    return cases


class TestSplitFee(unittest.TestCase):
    def test_perfect_pool_is_fifty_fifty(self):
        s, r = matched_session(_grid_of_geometries()[0])
        split = split_fee(s)
        self.assertAlmostEqual(split.pooled_fee, 9.0, places=2)
        self.assertAlmostEqual(split.initiator_fee, 4.5, places=2)
        self.assertAlmostEqual(split.partner_fee, 4.5, places=2)
        self.assertAlmostEqual(split.initiator_saving_pct, 50.0, places=1)

    def test_guarantees_hold_across_geometries(self):
        for a, b in _grid_of_geometries():
            with self.subTest(partner=b.name):
                s, r = matched_session((a, b))
                self.assertLessEqual(r.detour_ratio, MAX_DETOUR_RATIO)
                split = split_fee(s)
                # 1. 谁都不超过单人价
                self.assertLessEqual(split.initiator_fee, F)
                self.assertLessEqual(split.partner_fee, F)
                # 2. 双方等额受益，且省幅在 35%~50%
                self.assertAlmostEqual(
                    split.initiator_saving, split.partner_saving, places=1
                )
                for pct in (split.initiator_saving_pct, split.partner_saving_pct):
                    self.assertGreaterEqual(pct, 35.0)
                    self.assertLessEqual(pct, 50.0)
                # 3. 平台单趟计收在 [F, 1.3F]
                self.assertGreaterEqual(split.pooled_fee, F)
                self.assertLessEqual(split.pooled_fee, 1.3 * F + 0.01)
                # 分摊之和 = 合并价（无凭空增减的钱）
                self.assertAlmostEqual(
                    split.initiator_fee + split.partner_fee,
                    split.pooled_fee,
                    places=2,
                )

    def test_unmatched_session_raises(self):
        s = PinSession(
            store=STORE,
            base_delivery_fee=F,
            initiator=Party("initiator", "张三", GeoPoint("A", 39.98, 116.30), 40.0),
        )
        with self.assertRaises(ValueError):
            split_fee(s)


if __name__ == "__main__":
    unittest.main()
