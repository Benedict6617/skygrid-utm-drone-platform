import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, JSON, String
from sqlalchemy.orm import relationship

from app.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class TelemetryPoint(Base):
    """
    A single position/state report from a drone's flight controller,
    typically streamed every 1-2 seconds while airborne. Also carries
    optional detect-and-avoid (DAA) sensor contact reports so the
    deconfliction engine can react to tactical (in-flight) conflicts,
    not just strategic (pre-flight) ones.
    """

    __tablename__ = "telemetry_points"

    id = Column(String, primary_key=True, default=gen_uuid)
    drone_id = Column(String, ForeignKey("drones.id"), nullable=False)
    flight_plan_id = Column(String, ForeignKey("flight_plans.id"), nullable=True)

    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    altitude_m = Column(Float, nullable=False)
    heading_deg = Column(Float, default=0.0)
    ground_speed_mps = Column(Float, default=0.0)
    vertical_speed_mps = Column(Float, default=0.0)

    battery_percent = Column(Float, default=100.0)
    link_quality_percent = Column(Float, default=100.0)

    # Detect-and-avoid: list of nearby contacts detected by onboard
    # sensors (other aircraft, birds, obstacles), each with bearing,
    # distance, and closure rate. Stored as JSON for flexibility
    # across different DAA sensor vendors (radar, ADS-B, EO/IR, acoustic).
    daa_contacts = Column(JSON, nullable=True)

    drone = relationship("Drone", back_populates="telemetry_points")
