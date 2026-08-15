from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_operator
from app.database import get_db
from app.models.drone import Drone
from app.models.operator import Operator
from app.schemas.drone import DroneCreate, DroneOut, DroneStatusUpdate

router = APIRouter(prefix="/drones", tags=["Drones"])


@router.post("", response_model=DroneOut, status_code=201)
def register_drone(
    payload: DroneCreate,
    db: Session = Depends(get_db),
    current_operator: Operator = Depends(get_current_operator),
):
    existing = db.query(Drone).filter(Drone.serial_number == payload.serial_number).first()
    if existing:
        raise HTTPException(status_code=400, detail="A drone with this serial number is already registered.")

    drone = Drone(
        operator_id=current_operator.id,
        serial_number=payload.serial_number,
        faa_registration_number=payload.faa_registration_number,
        model=payload.model,
        manufacturer=payload.manufacturer,
        category=payload.category,
        max_speed_mps=payload.max_speed_mps,
        max_altitude_m=payload.max_altitude_m,
        max_flight_time_min=payload.max_flight_time_min,
        weight_kg=payload.weight_kg,
        has_detect_and_avoid=payload.has_detect_and_avoid,
        remote_id_broadcast=payload.remote_id_broadcast,
    )
    db.add(drone)
    db.commit()
    db.refresh(drone)
    return drone


@router.get("", response_model=List[DroneOut])
def list_my_drones(
    db: Session = Depends(get_db),
    current_operator: Operator = Depends(get_current_operator),
):
    return db.query(Drone).filter(Drone.operator_id == current_operator.id).all()


@router.get("/{drone_id}", response_model=DroneOut)
def get_drone(
    drone_id: str,
    db: Session = Depends(get_db),
    current_operator: Operator = Depends(get_current_operator),
):
    drone = db.query(Drone).filter(Drone.id == drone_id, Drone.operator_id == current_operator.id).first()
    if not drone:
        raise HTTPException(status_code=404, detail="Drone not found.")
    return drone


@router.patch("/{drone_id}/status", response_model=DroneOut)
def update_drone_status(
    drone_id: str,
    payload: DroneStatusUpdate,
    db: Session = Depends(get_db),
    current_operator: Operator = Depends(get_current_operator),
):
    drone = db.query(Drone).filter(Drone.id == drone_id, Drone.operator_id == current_operator.id).first()
    if not drone:
        raise HTTPException(status_code=404, detail="Drone not found.")
    drone.status = payload.status
    db.add(drone)
    db.commit()
    db.refresh(drone)
    return drone
