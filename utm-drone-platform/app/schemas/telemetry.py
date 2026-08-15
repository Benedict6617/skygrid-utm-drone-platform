from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class DAAContact(BaseModel):
    """A single detect-and-avoid sensor contact."""
    contact_type: str = Field(..., description="e.g. 'aircraft', 'bird', 'obstacle', 'unknown'")
    bearing_deg: float
    distance_m: float
    relative_altitude_m: float = 0.0
    closure_rate_mps: float = 0.0
    confidence: float = Field(0.8, ge=0, le=1)


class TelemetryIngest(BaseModel):
    drone_id: str
    flight_plan_id: Optional[str] = None
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    altitude_m: float = Field(..., ge=0)
    heading_deg: float = 0.0
    ground_speed_mps: float = 0.0
    vertical_speed_mps: float = 0.0
    battery_percent: float = Field(100.0, ge=0, le=100)
    link_quality_percent: float = Field(100.0, ge=0, le=100)
    daa_contacts: Optional[List[DAAContact]] = None


class TelemetryOut(BaseModel):
    id: str
    drone_id: str
    flight_plan_id: Optional[str]
    timestamp: datetime
    latitude: float
    longitude: float
    altitude_m: float
    heading_deg: float
    ground_speed_mps: float
    battery_percent: float
    link_quality_percent: float
    daa_contacts: Optional[list] = None

    class Config:
        from_attributes = True


class TelemetryAlert(BaseModel):
    """Result of evaluating a telemetry point for hazards."""
    drone_id: str
    alerts: List[str]
    recommended_action: str
    nearest_landing_zone_id: Optional[str] = None
