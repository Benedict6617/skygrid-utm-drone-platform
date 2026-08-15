from sqlalchemy import Boolean, Column, Float, String

from app.database import Base


class Airport(Base):
    """
    Reference data for airports/ATC facilities used to determine when
    a flight plan requires ATC coordination (typically within 5nm of
    a towered airport per LAANC facility maps).
    """

    __tablename__ = "airports"

    icao_code = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    elevation_m = Column(Float, default=0.0)
    airspace_class = Column(String, nullable=False)  # B, C, D, E
    has_atc_tower = Column(Boolean, default=True)
    laanc_facility_map_id = Column(String, nullable=True)
