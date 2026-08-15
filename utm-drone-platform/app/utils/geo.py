"""
Geospatial math helpers shared by the deconfliction, geofencing, and
emergency-landing services.

Uses the haversine formula for great-circle distance, which is
accurate enough for the sub-50km separations relevant to UAS
operations (drones don't fly far enough for ellipsoidal error to
matter at the precision this system needs).
"""
from __future__ import annotations

import math
from typing import Iterable, Sequence

EARTH_RADIUS_M = 6_371_000.0


def haversine_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two lat/lon points, in meters."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_M * c


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial bearing (degrees, 0-360) from point 1 to point 2."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_lambda = math.radians(lon2 - lon1)

    x = math.sin(d_lambda) * math.cos(phi2)
    y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(d_lambda)
    theta = math.atan2(x, y)
    return (math.degrees(theta) + 360) % 360


def point_in_polygon(lat: float, lon: float, polygon: Sequence[Sequence[float]]) -> bool:
    """
    Ray-casting point-in-polygon test.

    polygon: list of [lon, lat] pairs (GeoJSON ordering), first and
    last point need not be identical.
    """
    if len(polygon) < 3:
        return False

    inside = False
    n = len(polygon)
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i][0], polygon[i][1]
        xj, yj = polygon[j][0], polygon[j][1]
        intersects = ((yi > lat) != (yj > lat)) and (
            lon < (xj - xi) * (lat - yi) / (yj - yi + 1e-15) + xi
        )
        if intersects:
            inside = not inside
        j = i
    return inside


def circle_to_polygon(
    center_lat: float, center_lon: float, radius_m: float, num_points: int = 32
) -> list[list[float]]:
    """Tessellate a circle into a polygon ring of [lon, lat] points."""
    points = []
    for i in range(num_points):
        angle = 2 * math.pi * i / num_points
        d_lat = (radius_m * math.cos(angle)) / 111_320.0
        d_lon = (radius_m * math.sin(angle)) / (
            111_320.0 * math.cos(math.radians(center_lat)) + 1e-9
        )
        points.append([center_lon + d_lon, center_lat + d_lat])
    return points


def segment_min_distance_m(
    a1: tuple[float, float], a2: tuple[float, float], b1: tuple[float, float], b2: tuple[float, float]
) -> float:
    """
    Approximate minimum horizontal distance (meters) between two
    lat/lon path segments, sampled at fixed resolution. Good enough
    for tactical deconfliction over drone-scale distances without
    pulling in a full computational-geometry dependency.
    """
    best = float("inf")
    steps = 20
    for i in range(steps + 1):
        t = i / steps
        pa = (a1[0] + (a2[0] - a1[0]) * t, a1[1] + (a2[1] - a1[1]) * t)
        for j in range(steps + 1):
            u = j / steps
            pb = (b1[0] + (b2[0] - b1[0]) * u, b1[1] + (b2[1] - b1[1]) * u)
            d = haversine_distance_m(pa[0], pa[1], pb[0], pb[1])
            if d < best:
                best = d
    return best


def polyline_length_m(points: Iterable[tuple[float, float]]) -> float:
    points = list(points)
    total = 0.0
    for i in range(len(points) - 1):
        total += haversine_distance_m(points[i][0], points[i][1], points[i + 1][0], points[i + 1][1])
    return total
