"""
Flight path deconfliction engine.

Two layers, mirroring how real UTM systems separate concerns:

1. STRATEGIC deconfliction (this module's `check_strategic_conflicts`):
   run when a flight plan is submitted, before takeoff. Compares the
   proposed 4D route (lat/lon/alt/time) against every other APPROVED
   or ACTIVE flight plan sharing overlapping time and altitude, using
   segment-sampling to estimate minimum separation.

2. TACTICAL deconfliction (`evaluate_tactical_risk`): run continuously
   against live telemetry + onboard detect-and-avoid (DAA) sensor
   contacts while airborne, to catch conflicts that couldn't be known
   at planning time (a bird, a non-cooperative aircraft, GPS drift).

Both layers use the same minimum-separation standards
(MIN_HORIZONTAL_SEPARATION_M / MIN_VERTICAL_SEPARATION_M) so a plan
that clears strategic review is held to the same bar in flight.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.models.flight_plan import FlightPlan, FlightPlanStatus
from app.utils.geo import segment_min_distance_m


@dataclass
class ConflictRecord:
    other_flight_plan_id: str
    other_mission_name: str
    horizontal_separation_m: float
    vertical_separation_m: float
    overlapping_window: str
    severity: str  # "critical" | "warning"


@dataclass
class StrategicDeconflictionResult:
    is_clear: bool
    conflicts: List[ConflictRecord] = field(default_factory=list)
    checked_against_count: int = 0


def _time_windows_overlap(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    return a_start < b_end and b_start < a_end


def _altitude_bands_overlap(a_max: float, b_max: float) -> bool:
    # Each plan's operating band is modeled as [0, max_altitude] AGL
    # (small-UAS operations climb from the surface), so any two bands
    # necessarily overlap near ground level. This function exists as
    # an explicit hook for a future model with non-zero altitude
    # floors (e.g. package hand-off corridors); for now it always
    # passes and the real vertical-conflict decision is made from the
    # measured separation distance in the caller.
    return True


def check_strategic_conflicts(
    db: Session,
    candidate_waypoints: list[dict],
    candidate_start: datetime,
    candidate_end: datetime,
    candidate_max_altitude_m: float,
    exclude_flight_plan_id: Optional[str] = None,
) -> StrategicDeconflictionResult:
    """
    Compares a candidate route against all other active/approved
    flight plans for 4D conflicts (space + time + altitude).
    """
    min_h = settings.MIN_HORIZONTAL_SEPARATION_M
    min_v = settings.MIN_VERTICAL_SEPARATION_M

    query = db.query(FlightPlan).filter(
        FlightPlan.status.in_(
            [FlightPlanStatus.APPROVED, FlightPlanStatus.ACTIVE, FlightPlanStatus.LAANC_APPROVED]
        )
    )
    if exclude_flight_plan_id:
        query = query.filter(FlightPlan.id != exclude_flight_plan_id)

    others = query.all()
    conflicts: List[ConflictRecord] = []

    for other in others:
        if not _time_windows_overlap(
            candidate_start, candidate_end, other.planned_start_time, other.planned_end_time
        ):
            continue

        if not _altitude_bands_overlap(candidate_max_altitude_m, other.max_altitude_m):
            continue

        vertical_sep = abs(candidate_max_altitude_m - other.max_altitude_m)

        # Sample minimum horizontal separation across route segments.
        min_horizontal = float("inf")
        other_wps = other.waypoints
        for i in range(len(candidate_waypoints) - 1):
            a1 = (candidate_waypoints[i]["latitude"], candidate_waypoints[i]["longitude"])
            a2 = (candidate_waypoints[i + 1]["latitude"], candidate_waypoints[i + 1]["longitude"])
            for j in range(len(other_wps) - 1):
                b1 = (other_wps[j]["latitude"], other_wps[j]["longitude"])
                b2 = (other_wps[j + 1]["latitude"], other_wps[j + 1]["longitude"])
                d = segment_min_distance_m(a1, a2, b1, b2)
                min_horizontal = min(min_horizontal, d)

        if min_horizontal < min_h or vertical_sep < min_v:
            overlap_start = max(candidate_start, other.planned_start_time)
            overlap_end = min(candidate_end, other.planned_end_time)
            severity = "critical" if (min_horizontal < min_h * 0.5) else "warning"
            conflicts.append(
                ConflictRecord(
                    other_flight_plan_id=other.id,
                    other_mission_name=other.mission_name,
                    horizontal_separation_m=round(min_horizontal, 1),
                    vertical_separation_m=round(vertical_sep, 1),
                    overlapping_window=f"{overlap_start:%H:%M} - {overlap_end:%H:%M}",
                    severity=severity,
                )
            )

    return StrategicDeconflictionResult(
        is_clear=len(conflicts) == 0, conflicts=conflicts, checked_against_count=len(others)
    )


# ---------------------------------------------------------------------------
# Tactical (in-flight) deconfliction
# ---------------------------------------------------------------------------

@dataclass
class TacticalAlert:
    alert_type: str  # "daa_contact" | "airborne_conflict" | "geofence_breach"
    message: str
    severity: str  # "advisory" | "warning" | "critical"
    recommended_action: str


def evaluate_tactical_risk(
    own_lat: float,
    own_lon: float,
    own_alt_m: float,
    daa_contacts: Optional[list[dict]],
) -> List[TacticalAlert]:
    """
    Evaluates onboard detect-and-avoid sensor contacts reported in the
    latest telemetry frame and classifies risk using distance and
    closure rate — a simplified version of the well-clear geometry
    logic used in real DAA systems (e.g. DAIDALUS-style well-clear
    volumes), tuned for small-UAS operating envelopes rather than
    manned aircraft.
    """
    alerts: List[TacticalAlert] = []
    if not daa_contacts:
        return alerts

    min_h = settings.MIN_HORIZONTAL_SEPARATION_M

    for contact in daa_contacts:
        distance = contact.get("distance_m", 9999)
        closure = contact.get("closure_rate_mps", 0)
        contact_type = contact.get("contact_type", "unknown")

        time_to_closest_approach = distance / closure if closure > 0 else float("inf")

        if distance < min_h and closure > 0:
            alerts.append(
                TacticalAlert(
                    alert_type="daa_contact",
                    message=(
                        f"{contact_type.title()} contact at {distance:.0f}m, closing at "
                        f"{closure:.1f} m/s (est. {time_to_closest_approach:.0f}s to closest approach)."
                    ),
                    severity="critical" if time_to_closest_approach < 10 else "warning",
                    recommended_action=(
                        "Execute avoidance maneuver: climb/descend and hold, or divert to nearest "
                        "emergency landing zone if maneuvering is not safe."
                    ),
                )
            )
        elif distance < min_h * 2 and closure > 0:
            alerts.append(
                TacticalAlert(
                    alert_type="daa_contact",
                    message=f"{contact_type.title()} contact at {distance:.0f}m, closing.",
                    severity="advisory",
                    recommended_action="Monitor contact; be prepared to maneuver.",
                )
            )

    return alerts
