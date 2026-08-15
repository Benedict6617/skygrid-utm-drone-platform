import uuid
import enum
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Enum, Float, JSON, String, Text

from app.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class GeofenceType(str, enum.Enum):
    TFR = "temporary_flight_restriction"       # e.g. wildfire, VIP movement, stadium event
    PERMANENT_RESTRICTED = "permanent_restricted"  # e.g. airport core, prison, military base
    NO_FLY_NIGHT = "no_fly_zone_nighttime"
    NOISE_SENSITIVE = "noise_sensitive_zone"
    OPERATOR_DEFINED = "operator_defined"


class GeofenceSeverity(str, enum.Enum):
    ADVISORY = "advisory"      # informational, flight allowed
    RESTRICTED = "restricted"  # requires special authorization
    PROHIBITED = "prohibited"  # flight plans intersecting this are auto-rejected


class Geofence(Base):
    """
    A dynamic or static airspace restriction. Polygon is stored as a
    JSON list of [lon, lat] rings (GeoJSON-style) so it can represent
    arbitrary shapes (circles are pre-tessellated into polygons on
    creation for simplicity of geometry operations).
    """

    __tablename__ = "geofences"

    id = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    geofence_type = Column(Enum(GeofenceType), nullable=False)
    severity = Column(Enum(GeofenceSeverity), nullable=False)

    # GeoJSON-style polygon: [[lon, lat], [lon, lat], ...]
    polygon = Column(JSON, nullable=False)

    floor_altitude_m = Column(Float, default=0.0)
    ceiling_altitude_m = Column(Float, default=1000.0)

    effective_start = Column(DateTime, nullable=False)
    effective_end = Column(DateTime, nullable=True)  # null = indefinite

    issuing_authority = Column(String, default="SkyGrid UTM")  # e.g. "FAA", "Local PD", "SkyGrid UTM"
    source_reference = Column(String, nullable=True)  # NOTAM number etc.

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
