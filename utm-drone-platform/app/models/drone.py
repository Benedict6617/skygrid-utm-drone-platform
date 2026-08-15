import uuid
from datetime import datetime
import enum

from sqlalchemy import Boolean, Column, DateTime, Enum, Float, ForeignKey, String
from sqlalchemy.orm import relationship

from app.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class DroneStatus(str, enum.Enum):
    GROUNDED = "grounded"
    ARMED = "armed"
    AIRBORNE = "airborne"
    RETURNING = "returning"
    EMERGENCY = "emergency"
    MAINTENANCE = "maintenance"


class DroneCategory(str, enum.Enum):
    DELIVERY = "delivery"
    INSPECTION = "inspection"
    SURVEILLANCE = "surveillance"
    MAPPING = "mapping"
    AGRICULTURE = "agriculture"


class Drone(Base):
    """A single registered unmanned aircraft (UA) in an operator's fleet."""

    __tablename__ = "drones"

    id = Column(String, primary_key=True, default=gen_uuid)
    operator_id = Column(String, ForeignKey("operators.id"), nullable=False)

    serial_number = Column(String, unique=True, nullable=False, index=True)
    faa_registration_number = Column(String, unique=True, nullable=True)  # e.g. FA3XXXXXXX
    model = Column(String, nullable=False)
    manufacturer = Column(String, nullable=False)
    category = Column(Enum(DroneCategory), nullable=False)

    max_speed_mps = Column(Float, default=15.0)
    max_altitude_m = Column(Float, default=120.0)  # 400 ft AGL default Part 107 ceiling
    max_flight_time_min = Column(Float, default=30.0)
    weight_kg = Column(Float, default=2.5)

    has_detect_and_avoid = Column(Boolean, default=True)  # DAA sensor equipped
    remote_id_broadcast = Column(Boolean, default=True)  # FAA Remote ID compliant

    status = Column(Enum(DroneStatus), default=DroneStatus.GROUNDED)
    created_at = Column(DateTime, default=datetime.utcnow)

    operator = relationship("Operator", back_populates="drones")
    flight_plans = relationship("FlightPlan", back_populates="drone")
    telemetry_points = relationship("TelemetryPoint", back_populates="drone", cascade="all, delete-orphan")
