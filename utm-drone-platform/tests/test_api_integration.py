import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_health_check(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_register_and_login(client):
    payload = {
        "company_name": "Integration Test Co",
        "contact_email": "integration@test.example",
        "password": "SecurePass123",
    }
    resp = client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 201
    assert resp.json()["contact_email"] == payload["contact_email"]

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"contact_email": payload["contact_email"], "password": payload["password"]},
    )
    assert login_resp.status_code == 200
    assert "access_token" in login_resp.json()


def test_duplicate_registration_rejected(client, registered_operator):
    resp = client.post("/api/v1/auth/register", json=registered_operator)
    assert resp.status_code == 400


def test_login_wrong_password_rejected(client, registered_operator):
    resp = client.post(
        "/api/v1/auth/login",
        json={"contact_email": registered_operator["contact_email"], "password": "WrongPassword"},
    )
    assert resp.status_code == 401


def test_register_drone_requires_auth(client):
    resp = client.post("/api/v1/drones", json={
        "serial_number": "NOAUTH-0001",
        "model": "TestModel",
        "manufacturer": "TestMfr",
        "category": "delivery",
    })
    assert resp.status_code == 401


def test_full_flight_plan_lifecycle(client, auth_headers):
    # Register a drone
    drone_resp = client.post(
        "/api/v1/drones",
        json={
            "serial_number": "E2E-0001",
            "model": "TestModel",
            "manufacturer": "TestMfr",
            "category": "delivery",
            "max_altitude_m": 90,
        },
        headers=auth_headers,
    )
    assert drone_resp.status_code == 201
    drone_id = drone_resp.json()["id"]

    # Create a flight plan
    start = datetime.utcnow() + timedelta(hours=1)
    end = start + timedelta(minutes=20)
    plan_resp = client.post(
        "/api/v1/flight-plans",
        json={
            "drone_id": drone_id,
            "mission_name": "E2E Test Mission",
            "purpose": "delivery",
            "waypoints": [
                {"sequence": 1, "latitude": 39.9600, "longitude": -83.0000, "altitude_m": 0},
                {"sequence": 2, "latitude": 39.9700, "longitude": -83.0100, "altitude_m": 80},
            ],
            "planned_start_time": start.isoformat(),
            "planned_end_time": end.isoformat(),
            "max_altitude_m": 90,
            "priority": 5,
        },
        headers=auth_headers,
    )
    assert plan_resp.status_code == 201
    plan_id = plan_resp.json()["id"]
    assert plan_resp.json()["status"] == "draft"

    # Submit for review — result depends on simulated LAANC grid, but the
    # response must always contain a structured, well-formed result.
    review_resp = client.post(f"/api/v1/flight-plans/{plan_id}/submit-for-review", headers=auth_headers)
    assert review_resp.status_code == 200
    review = review_resp.json()
    assert "laanc" in review
    assert "final_status" in review


def test_geofence_creation_and_listing(client, auth_headers):
    resp = client.post(
        "/api/v1/geofences/circle",
        json={
            "name": "Test Circle TFR",
            "geofence_type": "temporary_flight_restriction",
            "severity": "prohibited",
            "center_latitude": 39.96,
            "center_longitude": -83.00,
            "radius_m": 500,
            "effective_start": datetime.utcnow().isoformat(),
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert len(resp.json()["polygon"]) >= 3

    list_resp = client.get("/api/v1/geofences")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) >= 1


def test_weather_conditions_endpoint(client):
    resp = client.get("/api/v1/weather/conditions", params={"latitude": 39.96, "longitude": -83.00})
    assert resp.status_code == 200
    body = resp.json()
    assert "wind_speed_mps" in body
    assert "is_flight_safe" in body


def test_telemetry_ingest_triggers_battery_emergency(client, auth_headers):
    drone_resp = client.post(
        "/api/v1/drones",
        json={
            "serial_number": "E2E-0002",
            "model": "TestModel",
            "manufacturer": "TestMfr",
            "category": "delivery",
        },
        headers=auth_headers,
    )
    drone_id = drone_resp.json()["id"]

    telemetry_resp = client.post(
        "/api/v1/telemetry/ingest",
        json={
            "drone_id": drone_id,
            "latitude": 39.96,
            "longitude": -83.00,
            "altitude_m": 50,
            "battery_percent": 8.0,
            "link_quality_percent": 100.0,
        },
    )
    assert telemetry_resp.status_code == 200
    body = telemetry_resp.json()
    assert body["recommended_action"] == "divert_to_emergency_landing_zone"
    assert any("EMERGENCY" in a for a in body["alerts"])
