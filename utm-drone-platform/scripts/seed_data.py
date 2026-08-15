"""
Seeds the database with realistic sample data for a small drone
operations business: three operator companies (delivery, inspection,
agricultural mapping), their fleets, reference airports, active
geofences/TFRs, emergency landing zones, and a batch of sample flight
plans covering both clean approvals and interesting edge cases
(a TFR conflict, a near-airport ATC-coordination case, etc).

Usage:
    python -m scripts.seed_data
"""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.security import hash_password  # noqa: E402
from app.database import SessionLocal, init_db  # noqa: E402
from app.models.airspace import Airport  # noqa: E402
from app.models.drone import Drone  # noqa: E402
from app.models.flight_plan import FlightPlan, FlightPlanStatus  # noqa: E402
from app.models.geofence import Geofence  # noqa: E402
from app.models.landing_zone import EmergencyLandingZone  # noqa: E402
from app.models.operator import Operator  # noqa: E402
from app.utils.geo import circle_to_polygon  # noqa: E402

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def load_json(filename: str):
    with open(DATA_DIR / filename, "r") as f:
        return json.load(f)


def seed_operators(db) -> dict[str, Operator]:
    operators = {}
    for item in load_json("sample_operators.json"):
        existing = db.query(Operator).filter(Operator.contact_email == item["contact_email"]).first()
        if existing:
            operators[item["contact_email"]] = existing
            continue
        op = Operator(
            company_name=item["company_name"],
            contact_email=item["contact_email"],
            hashed_password=hash_password(item["password"]),
            faa_certificate_number=item.get("faa_certificate_number"),
            phone_number=item.get("phone_number"),
        )
        db.add(op)
        db.flush()
        operators[item["contact_email"]] = op
    db.commit()
    print(f"  seeded {len(operators)} operators")
    return operators


def seed_drones(db, operators: dict[str, Operator]) -> dict[str, Drone]:
    drones = {}
    for item in load_json("sample_drones.json"):
        existing = db.query(Drone).filter(Drone.serial_number == item["serial_number"]).first()
        if existing:
            drones[item["serial_number"]] = existing
            continue
        drone = Drone(
            operator_id=operators[item["operator_email"]].id,
            serial_number=item["serial_number"],
            faa_registration_number=item.get("faa_registration_number"),
            model=item["model"],
            manufacturer=item["manufacturer"],
            category=item["category"],
            max_speed_mps=item["max_speed_mps"],
            max_altitude_m=item["max_altitude_m"],
            max_flight_time_min=item["max_flight_time_min"],
            weight_kg=item["weight_kg"],
            has_detect_and_avoid=item["has_detect_and_avoid"],
            remote_id_broadcast=item["remote_id_broadcast"],
        )
        db.add(drone)
        db.flush()
        drones[item["serial_number"]] = drone
    db.commit()
    print(f"  seeded {len(drones)} drones")
    return drones


def seed_airports(db) -> None:
    count = 0
    for item in load_json("sample_airports.json"):
        existing = db.query(Airport).filter(Airport.icao_code == item["icao_code"]).first()
        if existing:
            continue
        airport = Airport(
            icao_code=item["icao_code"],
            name=item["name"],
            latitude=item["latitude"],
            longitude=item["longitude"],
            elevation_m=item["elevation_m"],
            airspace_class=item["airspace_class"],
            has_atc_tower=item["has_atc_tower"],
            laanc_facility_map_id=item.get("laanc_facility_map_id"),
        )
        db.add(airport)
        count += 1
    db.commit()
    print(f"  seeded {count} airports")


def seed_geofences(db) -> None:
    now = datetime.utcnow()
    count = 0
    for item in load_json("sample_geofences.json"):
        existing = db.query(Geofence).filter(Geofence.name == item["name"]).first()
        if existing:
            continue
        polygon = circle_to_polygon(item["center_latitude"], item["center_longitude"], item["radius_m"])
        effective_start = now + timedelta(hours=item["effective_start_offset_hours"])
        effective_end = (
            now + timedelta(hours=item["effective_end_offset_hours"])
            if item.get("effective_end_offset_hours") is not None
            else None
        )
        fence = Geofence(
            name=item["name"],
            description=item.get("description"),
            geofence_type=item["geofence_type"],
            severity=item["severity"],
            polygon=polygon,
            floor_altitude_m=item["floor_altitude_m"],
            ceiling_altitude_m=item["ceiling_altitude_m"],
            effective_start=effective_start,
            effective_end=effective_end,
            issuing_authority=item["issuing_authority"],
            source_reference=item.get("source_reference"),
        )
        db.add(fence)
        count += 1
    db.commit()
    print(f"  seeded {count} geofences")


def seed_landing_zones(db) -> None:
    count = 0
    for item in load_json("sample_landing_zones.json"):
        existing = db.query(EmergencyLandingZone).filter(EmergencyLandingZone.name == item["name"]).first()
        if existing:
            continue
        zone = EmergencyLandingZone(
            name=item["name"],
            zone_type=item["zone_type"],
            latitude=item["latitude"],
            longitude=item["longitude"],
            radius_m=item["radius_m"],
            max_capacity=item["max_capacity"],
            is_available=item["is_available"],
            surface_type=item["surface_type"],
            population_density=item["population_density"],
        )
        db.add(zone)
        count += 1
    db.commit()
    print(f"  seeded {count} emergency landing zones")


def seed_flight_plans(db, operators: dict[str, Operator], drones: dict[str, Drone]) -> None:
    now = datetime.utcnow()
    count = 0
    for item in load_json("sample_flight_plans.json"):
        existing = db.query(FlightPlan).filter(FlightPlan.mission_name == item["mission_name"]).first()
        if existing:
            continue
        start = now + timedelta(minutes=item["start_offset_minutes"])
        end = start + timedelta(minutes=item["duration_minutes"])
        plan = FlightPlan(
            operator_id=operators[item["operator_email"]].id,
            drone_id=drones[item["drone_serial_number"]].id,
            mission_name=item["mission_name"],
            purpose=item["purpose"],
            waypoints=item["waypoints"],
            planned_start_time=start,
            planned_end_time=end,
            max_altitude_m=item["max_altitude_m"],
            priority=item["priority"],
            status=FlightPlanStatus.DRAFT,
        )
        db.add(plan)
        count += 1
    db.commit()
    print(f"  seeded {count} flight plans (status=draft; submit each for review via the API)")


def main():
    print("Initializing database schema...")
    init_db()

    db = SessionLocal()
    try:
        print("Seeding operators...")
        operators = seed_operators(db)
        print("Seeding drones...")
        drones = seed_drones(db, operators)
        print("Seeding airports...")
        seed_airports(db)
        print("Seeding geofences...")
        seed_geofences(db)
        print("Seeding emergency landing zones...")
        seed_landing_zones(db)
        print("Seeding flight plans...")
        seed_flight_plans(db, operators, drones)
        print("\nDone. Sample operator login credentials are in data/sample_operators.json")
    finally:
        db.close()


if __name__ == "__main__":
    main()
