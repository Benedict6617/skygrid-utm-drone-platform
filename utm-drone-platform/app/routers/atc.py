from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.airspace import Airport
from app.models.atc_event import ATCCoordinationEvent
from app.services.atc_service import find_nearby_airports

router = APIRouter(prefix="/atc", tags=["ATC Coordination"])


@router.get("/airports")
def list_airports(db: Session = Depends(get_db)):
    return db.query(Airport).all()


@router.get("/airports/nearby")
def nearby_airports(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    radius_m: float = Query(9260.0, gt=0),
    db: Session = Depends(get_db),
):
    return [a.__dict__ for a in find_nearby_airports(db, latitude, longitude, radius_m)]


@router.get("/coordination-events/{flight_plan_id}")
def get_coordination_events(flight_plan_id: str, db: Session = Depends(get_db)):
    return (
        db.query(ATCCoordinationEvent)
        .filter(ATCCoordinationEvent.flight_plan_id == flight_plan_id)
        .order_by(ATCCoordinationEvent.created_at.asc())
        .all()
    )
