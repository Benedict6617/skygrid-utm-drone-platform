import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.laanc_service import LAANCRequest, MockLAANCClient


def test_low_altitude_request_is_deterministic_and_consistent():
    client = MockLAANCClient()
    start = datetime(2026, 6, 1, 14, 0, 0)
    req = LAANCRequest(
        operator_id="op-1",
        drone_faa_registration="FA1234567",
        latitude=39.9560,
        longitude=-82.9435,
        max_altitude_m=10,  # very low altitude, should clear most grid ceilings
        start_time=start,
        end_time=start + timedelta(minutes=20),
    )
    resp1 = client.request_authorization(req)
    resp2 = client.request_authorization(req)
    # Same inputs must produce the same simulated outcome (deterministic hash-seeded).
    assert resp1.status == resp2.status
    assert resp1.approved == resp2.approved


def test_response_has_required_fields():
    client = MockLAANCClient()
    start = datetime(2026, 6, 1, 9, 0, 0)
    req = LAANCRequest(
        operator_id="op-2",
        drone_faa_registration="FA9999999",
        latitude=40.01,
        longitude=-83.05,
        max_altitude_m=90,
        start_time=start,
        end_time=start + timedelta(minutes=30),
    )
    resp = client.request_authorization(req)
    assert resp.status in ("approved", "denied", "further_coordination_required")
    assert isinstance(resp.approved, bool)
    if resp.approved:
        assert resp.authorization_id is not None
        assert resp.authorization_id.startswith("LAANC-")
    else:
        assert resp.reason is not None


def test_cancel_authorization_returns_true_in_mock_mode():
    client = MockLAANCClient()
    assert client.cancel_authorization("LAANC-12345") is True
