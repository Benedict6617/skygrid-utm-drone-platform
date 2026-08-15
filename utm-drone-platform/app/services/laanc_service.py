"""
FAA LAANC (Low Altitude Authorization and Notification Capability)
integration.

In production, a UTM platform acting as a USS (UAS Service Supplier)
submits authorization requests to the FAA's LAANC system for
operations in controlled airspace (Class B/C/D/E surface areas) near
airports. The real integration is a partner-specific REST/gRPC API
governed by an FAA Data Exchange Agreement.

This module provides:
  1. A clean `LAANCClient` interface any real vendor SDK can implement.
  2. A `MockLAANCClient` that simulates realistic FAA responses so the
     rest of the platform (and demos) can run without live credentials.
     Toggle via LAANC_MOCK_MODE in settings.

Swap in a real client by implementing `LAANCClient` and wiring it up
in `get_laanc_client()` below.
"""
from __future__ import annotations

import hashlib
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import httpx

from app.config import settings


@dataclass
class LAANCRequest:
    operator_id: str
    drone_faa_registration: Optional[str]
    latitude: float
    longitude: float
    max_altitude_m: float
    start_time: datetime
    end_time: datetime
    facility_map_id: Optional[str] = None


@dataclass
class LAANCResponse:
    approved: bool
    authorization_id: Optional[str]
    status: str  # "approved", "denied", "further_coordination_required"
    max_authorized_altitude_m: Optional[float]
    reason: Optional[str] = None
    raw: dict = field(default_factory=dict)


class LAANCClient(ABC):
    @abstractmethod
    def request_authorization(self, req: LAANCRequest) -> LAANCResponse: ...

    @abstractmethod
    def cancel_authorization(self, authorization_id: str) -> bool: ...


class MockLAANCClient(LAANCClient):
    """
    Deterministic-but-realistic LAANC simulator.

    Approval logic mirrors real-world LAANC facility map behavior:
    - Requests below the facility map's pre-authorized ceiling at that
      location are auto-approved instantly.
    - Requests above it, or in a "further coordination" zone, require
      manual review (simulated ~15% of the time near sensitive areas).
    - The response is deterministic per-request (hash-seeded) so demos
      and tests are reproducible, not random noise on every call.
    """

    def request_authorization(self, req: LAANCRequest) -> LAANCResponse:
        seed_str = f"{req.latitude:.4f}{req.longitude:.4f}{req.start_time.isoformat()}"
        seed = int(hashlib.sha256(seed_str.encode()).hexdigest(), 16) % (10**8)
        rng = random.Random(seed)

        # Simulate a facility map ceiling that varies by location (as
        # real LAANC grid cells do), typically 0-400ft.
        grid_ceiling_m = rng.choice([0, 30, 45, 60, 91, 122])

        if grid_ceiling_m == 0:
            return LAANCResponse(
                approved=False,
                authorization_id=None,
                status="denied",
                max_authorized_altitude_m=0,
                reason="Requested location falls within a 0ft grid cell (flight prohibited without further coordination).",
                raw={"grid_ceiling_m": grid_ceiling_m, "facility_map_id": req.facility_map_id},
            )

        if req.max_altitude_m <= grid_ceiling_m:
            auth_id = f"LAANC-{seed}"
            return LAANCResponse(
                approved=True,
                authorization_id=auth_id,
                status="approved",
                max_authorized_altitude_m=grid_ceiling_m,
                reason=None,
                raw={"grid_ceiling_m": grid_ceiling_m, "facility_map_id": req.facility_map_id},
            )

        # Above grid ceiling: further coordination required ~85% of the time,
        # occasionally auto-denied for the remainder.
        if rng.random() < 0.85:
            return LAANCResponse(
                approved=False,
                authorization_id=None,
                status="further_coordination_required",
                max_authorized_altitude_m=grid_ceiling_m,
                reason=(
                    f"Requested altitude {req.max_altitude_m:.0f}m exceeds the "
                    f"pre-authorized ceiling of {grid_ceiling_m:.0f}m for this grid cell. "
                    "Submit a further-coordination request to the controlling ATC facility."
                ),
                raw={"grid_ceiling_m": grid_ceiling_m, "facility_map_id": req.facility_map_id},
            )

        return LAANCResponse(
            approved=False,
            authorization_id=None,
            status="denied",
            max_authorized_altitude_m=grid_ceiling_m,
            reason="Request denied by facility map policy for this time window.",
            raw={"grid_ceiling_m": grid_ceiling_m, "facility_map_id": req.facility_map_id},
        )

    def cancel_authorization(self, authorization_id: str) -> bool:
        return True


class LiveLAANCClient(LAANCClient):
    """
    Skeleton for a real FAA-approved USS LAANC integration. Fill in
    `base_url`/auth per your Data Exchange Agreement and the specific
    partner API (e.g. AirMap, Aloft, OneSky) you're integrating
    through, since the FAA does not expose a single unified public
    LAANC endpoint directly to every operator.
    """

    def __init__(self):
        self.base_url = settings.LAANC_API_BASE_URL
        self.client_id = settings.LAANC_CLIENT_ID
        self.client_secret = settings.LAANC_CLIENT_SECRET

    def request_authorization(self, req: LAANCRequest) -> LAANCResponse:
        with httpx.Client(base_url=self.base_url, timeout=15) as client:
            resp = client.post(
                "/v1/authorizations",
                json={
                    "operator_id": req.operator_id,
                    "aircraft_registration": req.drone_faa_registration,
                    "latitude": req.latitude,
                    "longitude": req.longitude,
                    "max_altitude_m": req.max_altitude_m,
                    "start_time": req.start_time.isoformat(),
                    "end_time": req.end_time.isoformat(),
                    "facility_map_id": req.facility_map_id,
                },
                headers={"X-Client-Id": self.client_id, "X-Client-Secret": self.client_secret},
            )
            resp.raise_for_status()
            data = resp.json()
            return LAANCResponse(
                approved=data["approved"],
                authorization_id=data.get("authorization_id"),
                status=data["status"],
                max_authorized_altitude_m=data.get("max_authorized_altitude_m"),
                reason=data.get("reason"),
                raw=data,
            )

    def cancel_authorization(self, authorization_id: str) -> bool:
        with httpx.Client(base_url=self.base_url, timeout=15) as client:
            resp = client.delete(f"/v1/authorizations/{authorization_id}")
            return resp.status_code in (200, 204)


def get_laanc_client() -> LAANCClient:
    if settings.LAANC_MOCK_MODE:
        return MockLAANCClient()
    return LiveLAANCClient()
