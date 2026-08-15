import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.utils.geo import (
    bearing_deg,
    circle_to_polygon,
    haversine_distance_m,
    point_in_polygon,
    segment_min_distance_m,
)


def test_haversine_distance_zero_for_identical_points():
    assert haversine_distance_m(39.96, -83.00, 39.96, -83.00) == 0.0


def test_haversine_distance_known_approx():
    # Columbus, OH (39.9612, -82.9988) to Cincinnati, OH (39.1031, -84.5120)
    # approx great-circle distance is roughly 160 km.
    d = haversine_distance_m(39.9612, -82.9988, 39.1031, -84.5120)
    assert 150_000 < d < 175_000


def test_bearing_deg_north():
    # Point directly north should have a bearing near 0 degrees.
    b = bearing_deg(39.0, -83.0, 40.0, -83.0)
    assert b < 2 or b > 358


def test_point_in_polygon_simple_square():
    # Square roughly 0.01 deg on a side around (0,0)
    square = [[-0.01, -0.01], [0.01, -0.01], [0.01, 0.01], [-0.01, 0.01]]
    assert point_in_polygon(0.0, 0.0, square) is True
    assert point_in_polygon(1.0, 1.0, square) is False


def test_circle_to_polygon_points_near_radius():
    center_lat, center_lon, radius_m = 39.96, -83.00, 500.0
    polygon = circle_to_polygon(center_lat, center_lon, radius_m, num_points=16)
    assert len(polygon) == 16
    for lon, lat in polygon:
        d = haversine_distance_m(center_lat, center_lon, lat, lon)
        # Tessellated circle points should be close to the requested radius
        assert abs(d - radius_m) < 15  # small tolerance for spherical approx


def test_segment_min_distance_overlapping_segments_is_zero():
    d = segment_min_distance_m((39.0, -83.0), (39.01, -83.0), (39.0, -83.0), (39.01, -83.0))
    assert d < 1.0


def test_segment_min_distance_far_apart_segments():
    d = segment_min_distance_m((39.0, -83.0), (39.01, -83.0), (40.0, -84.0), (40.01, -84.0))
    assert d > 100_000
