import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models.drone import Drone
from app.models.flight_plan import FlightPlan, FlightPlanStatus
from app.models.operator import Operator
from app.services.deconfliction_service import check_strategic_conflicts


def _make_operator_and_drone(db):
    op = Operator(
        company_name="Conflict Test Co",
        contact_email="conflict@test.example",
        hashed_password="x",
    )
    db.add(op)
    db.flush()

    drone = Drone(
        operator_id=op.id,
        serial_number="TEST-0001",
        model="TestModel",
        manufacturer="TestMfr",
        category="delivery",
    )
    db.add(drone)
    db.flush()
    return op, drone


def test_no_conflict_when_no_other_flights(db_session):
    start = datetime(2026, 7, 1, 12, 0, 0)
    end = start + timedelta(minutes=15)
    waypoints = [
        {"sequence": 1, "latitude": 39.96, "longitude": -83.00, "altitude_m": 0},
        {"sequence": 2, "latitude": 39.97, "longitude": -83.01, "altitude_m": 80},
    ]
    result = check_strategic_conflicts(db_session, waypoints, start, end, 80)
    assert result.is_clear is True
    assert result.checked_against_count == 0


def test_conflict_detected_for_overlapping_close_route(db_session):
    op, drone = _make_operator_and_drone(db_session)

    start = datetime(2026, 7, 1, 12, 0, 0)
    end = start + timedelta(minutes=15)

    existing = FlightPlan(
        operator_id=op.id,
        drone_id=drone.id,
        mission_name="Existing Route",
        purpose="delivery",
        waypoints=[
            {"sequence": 1, "latitude": 39.9600, "longitude": -83.0000, "altitude_m": 0},
            {"sequence": 2, "latitude": 39.9610, "longitude": -83.0010, "altitude_m": 80},
        ],
        planned_start_time=start,
        planned_end_time=end,
        max_altitude_m=80,
        status=FlightPlanStatus.APPROVED,
    )
    db_session.add(existing)
    db_session.commit()

    # Candidate route runs essentially the same path, same time, same altitude:
    # should be flagged as a critical conflict (near-zero separation).
    candidate_waypoints = [
        {"sequence": 1, "latitude": 39.9600, "longitude": -83.0000, "altitude_m": 0},
        {"sequence": 2, "latitude": 39.9610, "longitude": -83.0010, "altitude_m": 80},
    ]
    result = check_strategic_conflicts(db_session, candidate_waypoints, start, end, 80)
    assert result.is_clear is False
    assert result.checked_against_count == 1
    assert result.conflicts[0].severity == "critical"


def test_no_conflict_when_routes_far_apart(db_session):
    op, drone = _make_operator_and_drone(db_session)

    start = datetime(2026, 7, 1, 12, 0, 0)
    end = start + timedelta(minutes=15)

    existing = FlightPlan(
        operator_id=op.id,
        drone_id=drone.id,
        mission_name="Existing Far Route",
        purpose="delivery",
        waypoints=[
            {"sequence": 1, "latitude": 39.9600, "longitude": -83.0000, "altitude_m": 0},
            {"sequence": 2, "latitude": 39.9610, "longitude": -83.0010, "altitude_m": 80},
        ],
        planned_start_time=start,
        planned_end_time=end,
        max_altitude_m=80,
        status=FlightPlanStatus.APPROVED,
    )
    db_session.add(existing)
    db_session.commit()

    # Candidate route is several km away — should be clear.
    candidate_waypoints = [
        {"sequence": 1, "latitude": 40.0800, "longitude": -83.1200, "altitude_m": 0},
        {"sequence": 2, "latitude": 40.0900, "longitude": -83.1300, "altitude_m": 80},
    ]
    result = check_strategic_conflicts(db_session, candidate_waypoints, start, end, 80)
    assert result.is_clear is True


def test_no_conflict_when_time_windows_dont_overlap(db_session):
    op, drone = _make_operator_and_drone(db_session)

    existing_start = datetime(2026, 7, 1, 8, 0, 0)
    existing_end = existing_start + timedelta(minutes=15)

    existing = FlightPlan(
        operator_id=op.id,
        drone_id=drone.id,
        mission_name="Morning Route",
        purpose="delivery",
        waypoints=[
            {"sequence": 1, "latitude": 39.9600, "longitude": -83.0000, "altitude_m": 0},
            {"sequence": 2, "latitude": 39.9610, "longitude": -83.0010, "altitude_m": 80},
        ],
        planned_start_time=existing_start,
        planned_end_time=existing_end,
        max_altitude_m=80,
        status=FlightPlanStatus.APPROVED,
    )
    db_session.add(existing)
    db_session.commit()

    # Same exact route, but hours later — no time overlap, so no conflict.
    later_start = datetime(2026, 7, 1, 18, 0, 0)
    later_end = later_start + timedelta(minutes=15)
    result = check_strategic_conflicts(
        db_session,
        existing.waypoints,
        later_start,
        later_end,
        80,
    )
    assert result.is_clear is True
