import uuid
import enum
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class FlightPlanStatus(str, enum.Enum):
    DRAFT = "draft"
    PENDING_LAANC = "pending_laanc"
    LAANC_APPROVED = "laanc_approved"
    LAANC_DENIED = "laanc_denied"
    PENDING_DECONFLICTION = "pending_deconfliction"
    CONFLICT_DETECTED = "conflict_detected"
    APPROVED = "approved"
    ACTIVE = "active"
    COMPLETED = "completed"
    ABORTED = "aborted"
    CANCELLED = "cancelled"


class FlightPlan(Base):
    """
    A submitted UAS operation plan: a route (sequence of waypoints),
    a time window, and an altitude block. Goes through LAANC
    authorization and strategic deconfliction before it can fly.
    """

    __tablename__ = "flight_plans"

    id = Column(String, primary_key=True, default=gen_uuid)
    operator_id = Column(String, ForeignKey("operators.id"), nullable=False)
    drone_id = Column(String, ForeignKey("drones.id"), nullable=False)

    mission_name = Column(String, nullable=False)
    purpose = Column(String, nullable=False)  # delivery / inspection / surveillance / mapping

    # Waypoints stored as JSON list of {lat, lon, alt_m, sequence}
    waypoints = Column(JSON, nullable=False)

    planned_start_time = Column(DateTime, nullable=False)
    planned_end_time = Column(DateTime, nullable=False)
    max_altitude_m = Column(Float, nullable=False)

    status = Column(Enum(FlightPlanStatus), default=FlightPlanStatus.DRAFT)

    # LAANC
    laanc_authorization_id = Column(String, nullable=True)
    laanc_response_payload = Column(JSON, nullable=True)

    # Deconfliction
    conflict_notes = Column(Text, nullable=True)
    priority = Column(Integer, default=5)  # 1 (highest, e.g. emergency/medical) - 10 (lowest)

    controlled_airspace_class = Column(String, nullable=True)  # e.g. "Class B", "Class D", None
    near_airport_code = Column(String, nullable=True)  # ICAO/FAA code if within 5nm of an airport

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    operator = relationship("Operator", back_populates="flight_plans")
    drone = relationship("Drone", back_populates="flight_plans")
