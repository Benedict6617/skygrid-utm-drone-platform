from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.models.geofence import GeofenceSeverity, GeofenceType


class GeofenceCreate(BaseModel):
    name: str
    description: Optional[str] = None
    geofence_type: GeofenceType
    severity: GeofenceSeverity
    polygon: List[List[float]] = Field(..., description="List of [lon, lat] points, min 3")
    floor_altitude_m: float = 0.0
    ceiling_altitude_m: float = 1000.0
    effective_start: datetime
    effective_end: Optional[datetime] = None
    issuing_authority: str = "SkyGrid UTM"
    source_reference: Optional[str] = None


class GeofenceCircleCreate(BaseModel):
    """Convenience input for the common case of a circular TFR."""
    name: str
    description: Optional[str] = None
    geofence_type: GeofenceType
    severity: GeofenceSeverity
    center_latitude: float
    center_longitude: float
    radius_m: float = Field(..., gt=0, le=50000)
    floor_altitude_m: float = 0.0
    ceiling_altitude_m: float = 1000.0
    effective_start: datetime
    effective_end: Optional[datetime] = None
    issuing_authority: str = "SkyGrid UTM"
    source_reference: Optional[str] = None


class GeofenceOut(BaseModel):
    id: str
    name: str
    description: Optional[str]
    geofence_type: GeofenceType
    severity: GeofenceSeverity
    polygon: list
    floor_altitude_m: float
    ceiling_altitude_m: float
    effective_start: datetime
    effective_end: Optional[datetime]
    issuing_authority: str
    source_reference: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
