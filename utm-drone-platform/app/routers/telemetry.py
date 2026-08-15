from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.drone import Drone, DroneStatus
from app.models.telemetry import TelemetryPoint
from app.schemas.telemetry import TelemetryAlert, TelemetryIngest, TelemetryOut
from app.services.deconfliction_service import evaluate_tactical_risk
from app.services.emergency_service import assess_emergency_condition, select_emergency_landing_zone

router = APIRouter(prefix="/telemetry", tags=["Telemetry & Detect-and-Avoid"])


@router.post("/ingest", response_model=TelemetryAlert)
def ingest_telemetry(payload: TelemetryIngest, db: Session = Depends(get_db)):
    """
    Accepts a live position/state report from a drone's flight
    controller. Persists it, evaluates tactical (DAA) risk, and
    checks for emergency-landing trigger conditions in a single pass —
    this is the hot path a real flight controller would call every
    1-2 seconds while airborne.
    """
    drone = db.query(Drone).filter(Drone.id == payload.drone_id).first()
    if not drone:
        raise HTTPException(status_code=404, detail="Drone not found.")

    daa_contacts = [c.model_dump() for c in payload.daa_contacts] if payload.daa_contacts else None

    point = TelemetryPoint(
        drone_id=payload.drone_id,
        flight_plan_id=payload.flight_plan_id,
        latitude=payload.latitude,
        longitude=payload.longitude,
        altitude_m=payload.altitude_m,
        heading_deg=payload.heading_deg,
        ground_speed_mps=payload.ground_speed_mps,
        vertical_speed_mps=payload.vertical_speed_mps,
        battery_percent=payload.battery_percent,
        link_quality_percent=payload.link_quality_percent,
        daa_contacts=daa_contacts,
    )
    db.add(point)
    db.commit()

    alerts: List[str] = []
    recommended_action = "continue"

    tactical_alerts = evaluate_tactical_risk(
        payload.latitude, payload.longitude, payload.altitude_m, daa_contacts
    )
    has_critical = any(a.severity == "critical" for a in tactical_alerts)
    for a in tactical_alerts:
        alerts.append(f"[{a.severity.upper()}] {a.message}")

    emergency_reason = assess_emergency_condition(
        payload.battery_percent, payload.link_quality_percent, has_critical
    )

    nearest_zone_id = None
    if emergency_reason:
        alerts.append(f"[EMERGENCY] {emergency_reason}")
        recommended_action = "divert_to_emergency_landing_zone"
        drone.status = DroneStatus.EMERGENCY
        db.add(drone)
        db.commit()

        assignment = select_emergency_landing_zone(db, payload.latitude, payload.longitude)
        if assignment:
            nearest_zone_id = assignment.zone_id
            alerts.append(
                f"Diverting to '{assignment.zone_name}' ({assignment.distance_m:.0f}m away). {assignment.reason}"
            )
        else:
            alerts.append("No emergency landing zone currently available — operator intervention required.")
    elif has_critical:
        recommended_action = "maneuver_to_avoid"
    elif tactical_alerts:
        recommended_action = "monitor"

    return TelemetryAlert(
        drone_id=payload.drone_id,
        alerts=alerts,
        recommended_action=recommended_action,
        nearest_landing_zone_id=nearest_zone_id,
    )


@router.get("/{drone_id}/history", response_model=List[TelemetryOut])
def get_telemetry_history(drone_id: str, limit: int = 100, db: Session = Depends(get_db)):
    points = (
        db.query(TelemetryPoint)
        .filter(TelemetryPoint.drone_id == drone_id)
        .order_by(TelemetryPoint.timestamp.desc())
        .limit(limit)
        .all()
    )
    return points
