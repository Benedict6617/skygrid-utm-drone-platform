import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, String
from sqlalchemy.orm import relationship

from app.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class Operator(Base):
    """
    A registered drone operator/business (Part 107 remote pilot or
    fleet-owning company) using the platform.
    """

    __tablename__ = "operators"

    id = Column(String, primary_key=True, default=gen_uuid)
    company_name = Column(String, nullable=False)
    contact_email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    faa_certificate_number = Column(String, nullable=True)  # Part 107 remote pilot cert
    phone_number = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    drones = relationship("Drone", back_populates="operator", cascade="all, delete-orphan")
    flight_plans = relationship("FlightPlan", back_populates="operator", cascade="all, delete-orphan")
