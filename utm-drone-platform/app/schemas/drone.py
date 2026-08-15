from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models.drone import DroneCategory, DroneStatus


class DroneCreate(BaseModel):
    serial_number: str = Field(..., min_length=3)
    faa_registration_number: Optional[str] = None
    model: str
    manufacturer: str
    category: DroneCategory
    max_speed_mps: float = Field(15.0, gt=0)
    max_altitude_m: float = Field(120.0, gt=0, le=400)  # FAA Part 107 ceiling is 400ft (~122m) AGL
    max_flight_time_min: float = Field(30.0, gt=0)
    weight_kg: float = Field(2.5, gt=0)
    has_detect_and_avoid: bool = True
    remote_id_broadcast: bool = True


class DroneOut(BaseModel):
    id: str
    operator_id: str
    serial_number: str
    faa_registration_number: Optional[str]
    model: str
    manufacturer: str
    category: DroneCategory
    max_speed_mps: float
    max_altitude_m: float
    max_flight_time_min: float
    weight_kg: float
    has_detect_and_avoid: bool
    remote_id_broadcast: bool
    status: DroneStatus
    created_at: datetime

    class Config:
        from_attributes = True


class DroneStatusUpdate(BaseModel):
    status: DroneStatus
