import uuid
import enum
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Enum, Float, String

from app.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class LandingZoneType(str, enum.Enum):
    DESIGNATED_PAD = "designated_pad"       # pre-approved rooftop/ground pad
    OPEN_FIELD = "open_field"
    PARKING_LOT = "parking_lot"
    EMERGENCY_ONLY = "emergency_only"       # reserved strictly for emergency diverts


class EmergencyLandingZone(Base):
    """
    A pre-surveyed site where a drone can be automatically diverted
    for a forced/emergency landing (e.g. battery critical, lost link,
    DAA-detected imminent collision, motor failure).
    """

    __tablename__ = "landing_zones"

    id = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String, nullable=False)
    zone_type = Column(Enum(LandingZoneType), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    radius_m = Column(Float, default=20.0)

    max_capacity = Column(Float, default=1)  # simultaneous emergency landings supported
    is_available = Column(Boolean, default=True)  # false while occupied/under maintenance
    surface_type = Column(String, default="paved")  # paved, grass, gravel, rooftop
    population_density = Column(String, default="low")  # low/medium/high - used for scoring

    created_at = Column(DateTime, default=datetime.utcnow)
