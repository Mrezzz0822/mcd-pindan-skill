"""McRoutePin (麦顺路) — 麦乐送顺路拼单 core library."""

from .fee import FeeSplit, render_share_card, split_fee
from .geo import encode_geohash, haversine_km, in_radius
from .matcher import (
    MAX_DETOUR_RATIO,
    MatchResult,
    evaluate,
    evaluate_candidate,
    geohash_bucket,
    rank_candidates,
    within_geofence,
)
from .models import GeoPoint, NearbyOrder, Party, PinSession, PinStatus, PinWall

__all__ = [
    "FeeSplit",
    "GeoPoint",
    "MatchResult",
    "MAX_DETOUR_RATIO",
    "NearbyOrder",
    "Party",
    "PinSession",
    "PinStatus",
    "PinWall",
    "encode_geohash",
    "evaluate",
    "evaluate_candidate",
    "geohash_bucket",
    "haversine_km",
    "in_radius",
    "rank_candidates",
    "render_share_card",
    "split_fee",
    "within_geofence",
]

__version__ = "2.0.0"
