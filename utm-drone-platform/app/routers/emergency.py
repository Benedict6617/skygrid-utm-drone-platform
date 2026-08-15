from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_operator
from app.database import get_db
from app.models.landing_zone import EmergencyLandingZone
from app.models.operator import Operator
from app.services.emergency_service import select_emergency_landing_zone

router = APIRouter(prefix="/emergency", tags=["Emergency Landing Zones"])


@router.get("/landing-zones")
def list_landing_zones(db: Session = Depends(get_db)):
    zones = db.query(EmergencyLandingZone).all()
    return zones


@router.get("/landing-zones/nearest")
def nearest_landing_zone(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    db: Session = Depends(get_db),
):
    assignment = select_emergency_landing_zone(db, latitude, longitude)
    if not assignment:
        raise HTTPException(status_code=404, detail="No emergency landing zone currently available.")
    return assignment.__dict__


@router.patch("/landing-zones/{zone_id}/availability")
def set_zone_availability(
    zone_id: str,
    is_available: bool,
    db: Session = Depends(get_db),
    current_operator: Operator = Depends(get_current_operator),
):
    zone = db.query(EmergencyLandingZone).filter(EmergencyLandingZone.id == zone_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail="Landing zone not found.")
    zone.is_available = is_available
    db.add(zone)
    db.commit()
    db.refresh(zone)
    return zone
