from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_operator
from app.database import get_db
from app.models.geofence import Geofence
from app.models.operator import Operator
from app.schemas.geofence import GeofenceCircleCreate, GeofenceCreate, GeofenceOut
from app.utils.geo import circle_to_polygon

router = APIRouter(prefix="/geofences", tags=["Geofences"])


@router.post("", response_model=GeofenceOut, status_code=201)
def create_geofence(
    payload: GeofenceCreate,
    db: Session = Depends(get_db),
    current_operator: Operator = Depends(get_current_operator),
):
    if len(payload.polygon) < 3:
        raise HTTPException(status_code=400, detail="Polygon requires at least 3 points.")

    fence = Geofence(
        name=payload.name,
        description=payload.description,
        geofence_type=payload.geofence_type,
        severity=payload.severity,
        polygon=payload.polygon,
        floor_altitude_m=payload.floor_altitude_m,
        ceiling_altitude_m=payload.ceiling_altitude_m,
        effective_start=payload.effective_start,
        effective_end=payload.effective_end,
        issuing_authority=payload.issuing_authority,
        source_reference=payload.source_reference,
    )
    db.add(fence)
    db.commit()
    db.refresh(fence)
    return fence


@router.post("/circle", response_model=GeofenceOut, status_code=201)
def create_circular_geofence(
    payload: GeofenceCircleCreate,
    db: Session = Depends(get_db),
    current_operator: Operator = Depends(get_current_operator),
):
    """Convenience endpoint: define a TFR as a center point + radius; tessellated into a polygon."""
    polygon = circle_to_polygon(payload.center_latitude, payload.center_longitude, payload.radius_m)
    fence = Geofence(
        name=payload.name,
        description=payload.description,
        geofence_type=payload.geofence_type,
        severity=payload.severity,
        polygon=polygon,
        floor_altitude_m=payload.floor_altitude_m,
        ceiling_altitude_m=payload.ceiling_altitude_m,
        effective_start=payload.effective_start,
        effective_end=payload.effective_end,
        issuing_authority=payload.issuing_authority,
        source_reference=payload.source_reference,
    )
    db.add(fence)
    db.commit()
    db.refresh(fence)
    return fence


@router.get("", response_model=List[GeofenceOut])
def list_geofences(db: Session = Depends(get_db)):
    return db.query(Geofence).filter(Geofence.is_active == True).all()  # noqa: E712


@router.get("/{geofence_id}", response_model=GeofenceOut)
def get_geofence(geofence_id: str, db: Session = Depends(get_db)):
    fence = db.query(Geofence).filter(Geofence.id == geofence_id).first()
    if not fence:
        raise HTTPException(status_code=404, detail="Geofence not found.")
    return fence


@router.delete("/{geofence_id}", status_code=204)
def deactivate_geofence(
    geofence_id: str,
    db: Session = Depends(get_db),
    current_operator: Operator = Depends(get_current_operator),
):
    fence = db.query(Geofence).filter(Geofence.id == geofence_id).first()
    if not fence:
        raise HTTPException(status_code=404, detail="Geofence not found.")
    fence.is_active = False
    db.add(fence)
    db.commit()
