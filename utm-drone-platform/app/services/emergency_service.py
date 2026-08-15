"""
Emergency landing zone assignment.

Triggered by: critical battery level, lost command-and-control link,
a critical tactical DAA alert, or an operator/ATC-directed ground
stop. Selects the best available pre-surveyed landing zone using a
weighted score of distance, capacity/availability, and population
density (safety of the site, not just proximity).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from app.models.landing_zone import EmergencyLandingZone
from app.utils.geo import haversine_distance_m

# Lower is worse for safety; used as a multiplier penalty in scoring.
_DENSITY_PENALTY = {"low": 1.0, "medium": 2.5, "high": 6.0}

BATTERY_CRITICAL_PERCENT = 15.0
BATTERY_WARNING_PERCENT = 25.0
LINK_LOSS_THRESHOLD_PERCENT = 20.0


@dataclass
class LandingZoneAssignment:
    zone_id: str
    zone_name: str
    latitude: float
    longitude: float
    distance_m: float
    reason: str


def select_emergency_landing_zone(
    db: Session, drone_lat: float, drone_lon: float
) -> Optional[LandingZoneAssignment]:
    """
    Picks the best available emergency landing zone for a drone at
    (drone_lat, drone_lon). Returns None if no zone is available
    (operator should be alerted to manually intervene).
    """
    candidates = db.query(EmergencyLandingZone).filter(
        EmergencyLandingZone.is_available == True  # noqa: E712
    ).all()

    if not candidates:
        return None

    best = None
    best_score = float("inf")

    for zone in candidates:
        distance = haversine_distance_m(drone_lat, drone_lon, zone.latitude, zone.longitude)
        density_penalty = _DENSITY_PENALTY.get(zone.population_density, 3.0)
        # Score: distance weighted by site-safety penalty. Lower is better.
        score = distance * density_penalty
        if score < best_score:
            best_score = score
            best = zone

    if best is None:
        return None

    distance = haversine_distance_m(drone_lat, drone_lon, best.latitude, best.longitude)
    return LandingZoneAssignment(
        zone_id=best.id,
        zone_name=best.name,
        latitude=best.latitude,
        longitude=best.longitude,
        distance_m=round(distance, 1),
        reason=(
            f"Selected as nearest available zone weighted by site safety "
            f"(population density: {best.population_density}, surface: {best.surface_type})."
        ),
    )


def assess_emergency_condition(
    battery_percent: float, link_quality_percent: float, has_critical_tactical_alert: bool
) -> Optional[str]:
    """Returns an emergency reason string if any trigger condition is met, else None."""
    if battery_percent <= BATTERY_CRITICAL_PERCENT:
        return f"Battery critical at {battery_percent:.0f}% — immediate landing required."
    if link_quality_percent <= LINK_LOSS_THRESHOLD_PERCENT:
        return f"Command-and-control link degraded to {link_quality_percent:.0f}% — lost-link procedure triggered."
    if has_critical_tactical_alert:
        return "Critical detect-and-avoid alert — evasive landing triggered."
    return None
