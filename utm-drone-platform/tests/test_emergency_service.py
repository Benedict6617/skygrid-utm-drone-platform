import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models.landing_zone import EmergencyLandingZone
from app.services.emergency_service import (
    assess_emergency_condition,
    select_emergency_landing_zone,
)


def test_selects_nearest_available_zone(db_session):
    near = EmergencyLandingZone(
        name="Near Zone",
        zone_type="open_field",
        latitude=39.9605,
        longitude=-83.0005,
        is_available=True,
        population_density="low",
        surface_type="grass",
    )
    far = EmergencyLandingZone(
        name="Far Zone",
        zone_type="open_field",
        latitude=40.5000,
        longitude=-84.0000,
        is_available=True,
        population_density="low",
        surface_type="grass",
    )
    db_session.add_all([near, far])
    db_session.commit()

    result = select_emergency_landing_zone(db_session, 39.9600, -83.0000)
    assert result is not None
    assert result.zone_name == "Near Zone"


def test_skips_unavailable_zones(db_session):
    unavailable_near = EmergencyLandingZone(
        name="Unavailable Near Zone",
        zone_type="open_field",
        latitude=39.9601,
        longitude=-83.0001,
        is_available=False,
        population_density="low",
        surface_type="grass",
    )
    available_far = EmergencyLandingZone(
        name="Available Far Zone",
        zone_type="open_field",
        latitude=40.2000,
        longitude=-83.5000,
        is_available=True,
        population_density="low",
        surface_type="grass",
    )
    db_session.add_all([unavailable_near, available_far])
    db_session.commit()

    result = select_emergency_landing_zone(db_session, 39.9600, -83.0000)
    assert result is not None
    assert result.zone_name == "Available Far Zone"


def test_prefers_low_density_over_slightly_closer_high_density(db_session):
    close_high_density = EmergencyLandingZone(
        name="Close High Density",
        zone_type="parking_lot",
        latitude=39.9605,
        longitude=-83.0005,
        is_available=True,
        population_density="high",
        surface_type="paved",
    )
    slightly_further_low_density = EmergencyLandingZone(
        name="Slightly Further Low Density",
        zone_type="open_field",
        latitude=39.9650,
        longitude=-83.0050,
        is_available=True,
        population_density="low",
        surface_type="grass",
    )
    db_session.add_all([close_high_density, slightly_further_low_density])
    db_session.commit()

    result = select_emergency_landing_zone(db_session, 39.9600, -83.0000)
    assert result.zone_name == "Slightly Further Low Density"


def test_returns_none_when_no_zones_available(db_session):
    result = select_emergency_landing_zone(db_session, 39.9600, -83.0000)
    assert result is None


def test_assess_emergency_condition_battery_critical():
    reason = assess_emergency_condition(10.0, 100.0, False)
    assert reason is not None
    assert "Battery critical" in reason


def test_assess_emergency_condition_link_loss():
    reason = assess_emergency_condition(80.0, 5.0, False)
    assert reason is not None
    assert "link" in reason.lower()


def test_assess_emergency_condition_nominal_returns_none():
    reason = assess_emergency_condition(80.0, 100.0, False)
    assert reason is None
