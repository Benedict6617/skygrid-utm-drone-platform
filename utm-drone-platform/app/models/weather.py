import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, String

from app.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class WeatherObservation(Base):
    """
    A cached weather snapshot for a location, pulled from the
    external weather provider. Cached to avoid hammering the provider
    API on every flight-plan check and to give the deconfliction
    engine a consistent read within a planning cycle.
    """

    __tablename__ = "weather_observations"

    id = Column(String, primary_key=True, default=gen_uuid)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)

    observed_at = Column(DateTime, default=datetime.utcnow)
    wind_speed_mps = Column(Float, nullable=False)
    wind_gust_mps = Column(Float, nullable=True)
    wind_direction_deg = Column(Float, nullable=True)
    precipitation_mm_hr = Column(Float, default=0.0)
    visibility_km = Column(Float, default=10.0)
    temperature_c = Column(Float, nullable=True)

    flight_category = Column(String, default="VFR")  # VFR / MVFR / IFR / LIFR style rating
    source = Column(String, default="weather.gov")
