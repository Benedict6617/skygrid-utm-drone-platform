import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models.geofence import Geofence
from app.services.geofence_service import check_route_against_geofences
from app.utils.geo import circle_to_polygon


def _add_geofence(db, name, severity, center_lat, center_lon, radius_m, start, end):
    fence = Geofence(
        name=name,
        geofence_type="temporary_flight_restriction",
        severity=severity,
        polygon=circle_to_polygon(center_lat, center_lon, radius_m),
        floor_altitude_m=0,
        ceiling_altitude_m=500,
        effective_start=start,
        effective_end=end,
        is_active=True,
    )
    db.add(fence)
    db.commit()
    return fence


def test_route_clear_when_no_geofences(db_session):
    start = datetime(2026, 7, 1, 12, 0, 0)
    end = start + timedelta(minutes=15)
    waypoints = [
        {"latitude": 39.96, "longitude": -83.00},
        {"latitude": 39.97, "longitude": -83.01},
    ]
    result = check_route_against_geofences(db_session, waypoints, start, end, 80)
    assert result.is_clear is True


def test_route_blocked_by_prohibited_tfr_intersection(db_session):
    start = datetime(2026, 7, 1, 12, 0, 0)
    end = start + timedelta(minutes=15)

    # TFR centered exactly on the route's first waypoint.
    _add_geofence(
        db_session, "Test TFR", "prohibited", 39.9600, -83.0000, 1000, start - timedelta(hours=1), end + timedelta(hours=1)
    )

    waypoints = [
        {"latitude": 39.9600, "longitude": -83.0000},
        {"latitude": 39.9700, "longitude": -83.0100},
    ]
    result = check_route_against_geofences(db_session, waypoints, start, end, 80)
    assert result.is_clear is False
    assert len(result.blocking) == 1


def test_route_not_blocked_when_fence_inactive_outside_time_window(db_session):
    start = datetime(2026, 7, 1, 12, 0, 0)
    end = start + timedelta(minutes=15)

    # TFR that expired well before this flight's window.
    fence_start = datetime(2026, 6, 1, 0, 0, 0)
    fence_end = datetime(2026, 6, 2, 0, 0, 0)
    _add_geofence(db_session, "Expired TFR", "prohibited", 39.9600, -83.0000, 1000, fence_start, fence_end)

    waypoints = [
        {"latitude": 39.9600, "longitude": -83.0000},
        {"latitude": 39.9700, "longitude": -83.0100},
    ]
    result = check_route_against_geofences(db_session, waypoints, start, end, 80)
    assert result.is_clear is True


def test_advisory_severity_does_not_block_route(db_session):
    start = datetime(2026, 7, 1, 12, 0, 0)
    end = start + timedelta(minutes=15)
    _add_geofence(
        db_session, "Noise Advisory Zone", "advisory", 39.9600, -83.0000, 1000, start - timedelta(hours=1), end + timedelta(hours=1)
    )

    waypoints = [
        {"latitude": 39.9600, "longitude": -83.0000},
        {"latitude": 39.9700, "longitude": -83.0100},
    ]
    result = check_route_against_geofences(db_session, waypoints, start, end, 80)
    assert result.is_clear is True
    assert len(result.advisories) == 1
