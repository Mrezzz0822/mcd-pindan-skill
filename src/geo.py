"""Geographic primitives for McRoutePin (麦顺路).

Pure-standard-library implementation of the pieces a delivery-carpool
matcher needs:

- haversine distance between two WGS-84 coordinates
- geohash encoding (for coarse 2 km grid bucketing)
- point-in-circle test

No external dependencies on purpose: the skill must be able to run its
matching math anywhere, including inside an Agent sandbox that only has
the Python standard library.
"""

from __future__ import annotations

import math

EARTH_RADIUS_KM = 6371.0088

# Base32 character set used by the geohash alphabet.
_BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres between two coordinates."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2.0) ** 2
    )
    return 2.0 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def encode_geohash(lat: float, lon: float, precision: int = 6) -> str:
    """Encode a coordinate into a geohash string.

    Precision 6 gives cells of roughly ±0.6 km, a good neighbour-search
    bucket for a 2 km matching radius.
    """
    lat_interval = [-90.0, 90.0]
    lon_interval = [-180.0, 180.0]
    geohash = []
    bits = 0
    bit = 0
    even = True
    while len(geohash) < precision:
        if even:
            mid = (lon_interval[0] + lon_interval[1]) / 2.0
            if lon >= mid:
                bits |= 1 << (4 - bit)
                lon_interval[0] = mid
            else:
                lon_interval[1] = mid
        else:
            mid = (lat_interval[0] + lat_interval[1]) / 2.0
            if lat >= mid:
                bits |= 1 << (4 - bit)
                lat_interval[0] = mid
            else:
                lat_interval[1] = mid
        even = not even
        if bit < 4:
            bit += 1
        else:
            geohash.append(_BASE32[bits])
            bits = 0
            bit = 0
    return "".join(geohash)


def in_radius(
    center_lat: float,
    center_lon: float,
    point_lat: float,
    point_lon: float,
    radius_km: float,
) -> bool:
    """True when ``point`` lies within ``radius_km`` of ``center``."""
    return haversine_km(center_lat, center_lon, point_lat, point_lon) <= radius_km
