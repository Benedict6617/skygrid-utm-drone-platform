"""
Coordination with traditional Air Traffic Control for operations near
towered airports.

Real-world equivalent: LAANC already encodes most of this via facility
maps, but operations that exceed the facility map ceiling, occur at
non-LAANC-participating airports, or require ad-hoc coordination
(e.g. a temporary tower closure, an active emergency at the airport)
still need a message logged to/from the facility. This module
determines *when* that coordination is required and records the
resulting exchange.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.models.airspace import Airport
from app.models.atc_event import ATCCoordinationEvent, ATCEventType
from app.utils.geo import haversine_distance_m

# Standard LAANC/ATC coordination radius around towered airports.
ATC_COORDINATION_RADIUS_M = 9_260.0  # 5 nautical miles


@dataclass
class NearbyAirport:
    icao_code: str
    name: str
    distance_m: float
    airspace_class: str


def find_nearby_airports(db: Session, lat: float, lon: float, radius_m: float = ATC_COORDINATION_RADIUS_M) -> List[NearbyAirport]:
    airports = db.query(Airport).all()
    nearby = []
    for ap in airports:
        d = haversine_distance_m(lat, lon, ap.latitude, ap.longitude)
        if d <= radius_m:
            nearby.append(
                NearbyAirport(icao_code=ap.icao_code, name=ap.name, distance_m=round(d, 1), airspace_class=ap.airspace_class)
            )
    return sorted(nearby, key=lambda a: a.distance_m)


def requires_atc_coordination(db: Session, waypoints: list[dict]) -> Optional[NearbyAirport]:
    """Returns the closest airport requiring coordination, or None if clear of all towered fields."""
    for wp in waypoints:
        nearby = find_nearby_airports(db, wp["latitude"], wp["longitude"])
        if nearby:
            return nearby[0]
    return None


def log_coordination_request(
    db: Session, flight_plan_id: str, airport_icao_code: str, message: str
) -> ATCCoordinationEvent:
    event = ATCCoordinationEvent(
        flight_plan_id=flight_plan_id,
        airport_icao_code=airport_icao_code,
        event_type=ATCEventType.COORDINATION_REQUEST,
        message=message,
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    # In mock mode we auto-approve after logging the request, simulating
    # a facility that accepts standard near-airport small-UAS operations
    # below the facility ceiling. A live integration would instead await
    # an inbound message/webhook from the ATC facility feed.
    if settings.ATC_MOCK_MODE:
        approval = ATCCoordinationEvent(
            flight_plan_id=flight_plan_id,
            airport_icao_code=airport_icao_code,
            event_type=ATCEventType.COORDINATION_APPROVED,
            message=f"Auto-approved in simulation mode for {airport_icao_code}.",
        )
        db.add(approval)
        db.commit()

    return event
