"""Tests for geo primitives (haversine, geohash, radius)."""

import math
import unittest

from src.geo import encode_geohash, haversine_km, in_radius


class TestHaversine(unittest.TestCase):
    def test_zero_distance(self):
        self.assertAlmostEqual(haversine_km(39.9, 116.3, 39.9, 116.3), 0.0)

    def test_known_beijing_distance(self):
        # 天安门(39.9087, 116.3975) -> 中关村(39.9839, 116.3163) 约 10.3 km
        d = haversine_km(39.9087, 116.3975, 39.9839, 116.3163)
        self.assertTrue(9.5 < d < 11.0, f"expected ~10.3km, got {d:.2f}")

    def test_symmetry(self):
        d1 = haversine_km(39.9, 116.3, 39.95, 116.35)
        d2 = haversine_km(39.95, 116.35, 39.9, 116.3)
        self.assertAlmostEqual(d1, d2)

    def test_one_degree_of_latitude_is_about_111km(self):
        d = haversine_km(40.0, 116.0, 41.0, 116.0)
        self.assertTrue(110.0 < d < 112.0, f"got {d:.2f}")


class TestGeohash(unittest.TestCase):
    def test_beijing_center_encoding(self):
        # 北京市中心附近的 6 位 geohash 以 wx4 开头
        self.assertTrue(encode_geohash(39.9, 116.4, 6).startswith("wx4"))

    def test_nearby_points_share_prefix(self):
        a = encode_geohash(39.98390, 116.30575, 6)
        b = encode_geohash(39.98390, 116.30460, 6)
        self.assertEqual(a[:5], b[:5])


class TestInRadius(unittest.TestCase):
    def test_inside(self):
        self.assertTrue(in_radius(39.9, 116.3, 39.901, 116.301, 2.0))

    def test_outside(self):
        self.assertFalse(in_radius(39.9, 116.3, 40.05, 116.45, 2.0))


if __name__ == "__main__":
    unittest.main()
