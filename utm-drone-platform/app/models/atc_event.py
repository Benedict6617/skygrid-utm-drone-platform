import uuid
import enum
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, ForeignKey, String, Text

from app.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class ATCEventType(str, enum.Enum):
    COORDINATION_REQUEST = "coordination_request"
    COORDINATION_APPROVED = "coordination_approved"
    COORDINATION_DENIED = "coordination_denied"
    ADVISORY_ISSUED = "advisory_issued"
    OPERATION_HALTED = "operation_halted"  # ATC-directed ground stop for the flight plan


class ATCCoordinationEvent(Base):
    """
    Log of coordination messages exchanged with traditional Air
    Traffic Control for operations near towered airports (Class B/C/D
    surface areas). In production this integrates with an FAA-approved
    facility feed; here it models the message log regardless of
    transport.
    """

    __tablename__ = "atc_coordination_events"

    id = Column(String, primary_key=True, default=gen_uuid)
    flight_plan_id = Column(String, ForeignKey("flight_plans.id"), nullable=False)
    airport_icao_code = Column(String, ForeignKey("airports.icao_code"), nullable=False)

    event_type = Column(Enum(ATCEventType), nullable=False)
    message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
