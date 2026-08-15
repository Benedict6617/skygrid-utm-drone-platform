"""
Dynamic geofencing: checks whether a proposed route intersects any
active restriction (TFRs, permanent restricted areas, operator-defined
keep-outs) at the relevant altitude and time window.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List

from sqlalchemy.orm import Session

from app.models.geofence import Geofence, GeofenceSeverity
from app.utils.geo import point_in_polygon


@dataclass
class GeofenceViolation:
    geofence_id: str
    geofence_name: str
    severity: str
    reason: str


@dataclass
class GeofenceCheckResult:
    is_clear: bool
    blocking: List[GeofenceViolation]
    advisories: List[GeofenceViolation]


def _time_overlaps(fence: Geofence, start: datetime, end: datetime) -> bool:
    if fence.effective_start and end < fence.effective_start:
        return False
    if fence.effective_end and start > fence.effective_end:
        return False
    return True


def _altitude_overlaps(fence: Geofence, max_altitude_m: float) -> bool:
    return not (max_altitude_m < fence.floor_altitude_m or 0 > fence.ceiling_altitude_m)


def check_route_against_geofences(
    db: Session,
    waypoints: list[dict],
    start_time: datetime,
    end_time: datetime,
    max_altitude_m: float,
) -> GeofenceCheckResult:
    """
    Checks every waypoint (and, coarsely, the straight-line segments
    between consecutive waypoints via midpoint sampling) against all
    active geofences for spatial, temporal, and altitude overlap.
    """
    active_fences = db.query(Geofence).filter(Geofence.is_active == True).all()  # noqa: E712

    blocking: List[GeofenceViolation] = []
    advisories: List[GeofenceViolation] = []
    seen_fence_ids: set[str] = set()

    # Build sample points: waypoints + midpoints between consecutive waypoints,
    # giving reasonable coverage of the route without a full geometry engine.
    sample_points: list[tuple[float, float]] = []
    for i, wp in enumerate(waypoints):
        sample_points.append((wp["latitude"], wp["longitude"]))
        if i + 1 < len(waypoints):
            nxt = waypoints[i + 1]
            mid_lat = (wp["latitude"] + nxt["latitude"]) / 2
            mid_lon = (wp["longitude"] + nxt["longitude"]) / 2
            sample_points.append((mid_lat, mid_lon))

    for fence in active_fences:
        if fence.id in seen_fence_ids:
            continue
        if not _time_overlaps(fence, start_time, end_time):
            continue
        if not _altitude_overlaps(fence, max_altitude_m):
            continue

        hit = any(point_in_polygon(lat, lon, fence.polygon) for lat, lon in sample_points)
        if not hit:
            continue

        seen_fence_ids.add(fence.id)
        if fence.effective_end:
            window = (
                f"{fence.effective_start:%Y-%m-%d %H:%M} - {fence.effective_end:%Y-%m-%d %H:%M}"
            )
        else:
            window = f"active indefinitely from {fence.effective_start:%Y-%m-%d %H:%M}"
        violation = GeofenceViolation(
            geofence_id=fence.id,
            geofence_name=fence.name,
            severity=fence.severity,
            reason=f"Route intersects '{fence.name}' ({fence.geofence_type}), {window}.",
        )

        if fence.severity == GeofenceSeverity.PROHIBITED:
            blocking.append(violation)
        elif fence.severity == GeofenceSeverity.RESTRICTED:
            blocking.append(violation)
        else:
            advisories.append(violation)

    return GeofenceCheckResult(is_clear=len(blocking) == 0, blocking=blocking, advisories=advisories)
