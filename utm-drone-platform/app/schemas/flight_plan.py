from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.models.flight_plan import FlightPlanStatus


class Waypoint(BaseModel):
    sequence: int
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    altitude_m: float = Field(..., ge=0, le=400)


class FlightPlanCreate(BaseModel):
    drone_id: str
    mission_name: str
    purpose: str  # delivery / inspection / surveillance / mapping
    waypoints: List[Waypoint]
    planned_start_time: datetime
    planned_end_time: datetime
    max_altitude_m: float = Field(..., gt=0, le=400)
    priority: int = Field(5, ge=1, le=10)

    @field_validator("waypoints")
    @classmethod
    def at_least_two_waypoints(cls, v):
        if len(v) < 2:
            raise ValueError("A flight plan needs at least 2 waypoints (origin + destination)")
        return v

    @field_validator("planned_end_time")
    @classmethod
    def end_after_start(cls, v, info):
        start = info.data.get("planned_start_time")
        if start and v <= start:
            raise ValueError("planned_end_time must be after planned_start_time")
        return v


class FlightPlanOut(BaseModel):
    id: str
    operator_id: str
    drone_id: str
    mission_name: str
    purpose: str
    waypoints: list
    planned_start_time: datetime
    planned_end_time: datetime
    max_altitude_m: float
    status: FlightPlanStatus
    laanc_authorization_id: Optional[str] = None
    conflict_notes: Optional[str] = None
    priority: int
    controlled_airspace_class: Optional[str] = None
    near_airport_code: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class FlightPlanReviewResult(BaseModel):
    """Aggregated result returned after submitting a flight plan for review."""
    flight_plan: FlightPlanOut
    laanc_result: dict
    weather_result: dict
    deconfliction_result: dict
    atc_coordination_required: bool
