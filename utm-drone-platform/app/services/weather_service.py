"""
Weather integration used to gate flight-plan approval and to raise
in-flight alerts.

Real deployments should point WEATHER_API_BASE_URL at a provider such
as api.weather.gov (US National Weather Service, free/public) or a
commercial aviation-weather vendor. WEATHER_MOCK_MODE=true (the
default for local dev/demo) uses a lightweight deterministic
simulator so the platform is fully runnable offline.
"""
from __future__ import annotations

import hashlib
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

import httpx

from app.config import settings

# Small-UAS operating limits used for go/no-go recommendations.
# These mirror common Part 107 operator SOPs, not hard FAA limits
# (Part 107 itself only mandates 3 statute miles visibility and
# clear-of-clouds distances) — small business operators typically
# adopt tighter internal thresholds for airframe safety.
MAX_SAFE_WIND_MPS = 10.7          # ~24 mph sustained
MAX_SAFE_GUST_MPS = 13.4          # ~30 mph gust
MAX_SAFE_PRECIP_MM_HR = 2.5       # light rain threshold
MIN_SAFE_VISIBILITY_KM = 4.8      # ~3 statute miles


@dataclass
class WeatherSnapshot:
    latitude: float
    longitude: float
    wind_speed_mps: float
    wind_gust_mps: float
    wind_direction_deg: float
    precipitation_mm_hr: float
    visibility_km: float
    temperature_c: float
    flight_category: str
    observed_at: datetime
    source: str


@dataclass
class WeatherAssessment:
    snapshot: WeatherSnapshot
    is_flight_safe: bool
    warnings: list[str]


class WeatherProvider(ABC):
    @abstractmethod
    def get_current_conditions(self, lat: float, lon: float) -> WeatherSnapshot: ...


class MockWeatherProvider(WeatherProvider):
    """Deterministic simulated weather, seeded by location + hour."""

    def get_current_conditions(self, lat: float, lon: float) -> WeatherSnapshot:
        now = datetime.utcnow()
        seed_str = f"{lat:.2f}{lon:.2f}{now.strftime('%Y%m%d%H')}"
        seed = int(hashlib.sha256(seed_str.encode()).hexdigest(), 16) % (10**8)
        rng = random.Random(seed)

        wind_speed = round(rng.uniform(0.5, 14.0), 1)
        wind_gust = round(wind_speed + rng.uniform(0, 6.0), 1)
        precip = round(rng.choices([0.0, 0.5, 2.0, 6.0], weights=[70, 15, 10, 5])[0], 1)
        visibility = round(rng.uniform(3.0, 16.0), 1)
        temp = round(rng.uniform(-5, 32), 1)

        if precip > 4 or visibility < 3:
            category = "IFR"
        elif precip > 0 or visibility < 8:
            category = "MVFR"
        else:
            category = "VFR"

        return WeatherSnapshot(
            latitude=lat,
            longitude=lon,
            wind_speed_mps=wind_speed,
            wind_gust_mps=wind_gust,
            wind_direction_deg=round(rng.uniform(0, 359), 0),
            precipitation_mm_hr=precip,
            visibility_km=visibility,
            temperature_c=temp,
            flight_category=category,
            observed_at=now,
            source="mock-weather-sim",
        )


class LiveWeatherProvider(WeatherProvider):
    """Thin client for a real weather API (e.g. api.weather.gov points/gridpoint flow)."""

    def __init__(self):
        self.base_url = settings.WEATHER_API_BASE_URL
        self.api_key = settings.WEATHER_API_KEY

    def get_current_conditions(self, lat: float, lon: float) -> WeatherSnapshot:
        with httpx.Client(base_url=self.base_url, timeout=15) as client:
            resp = client.get(
                "/current",
                params={"lat": lat, "lon": lon},
                headers={"Authorization": f"Bearer {self.api_key}"} if self.api_key else {},
            )
            resp.raise_for_status()
            d = resp.json()
            return WeatherSnapshot(
                latitude=lat,
                longitude=lon,
                wind_speed_mps=d["wind_speed_mps"],
                wind_gust_mps=d.get("wind_gust_mps", d["wind_speed_mps"]),
                wind_direction_deg=d.get("wind_direction_deg", 0.0),
                precipitation_mm_hr=d.get("precipitation_mm_hr", 0.0),
                visibility_km=d.get("visibility_km", 10.0),
                temperature_c=d.get("temperature_c", 15.0),
                flight_category=d.get("flight_category", "VFR"),
                observed_at=datetime.utcnow(),
                source=d.get("source", "live-weather-api"),
            )


def get_weather_provider() -> WeatherProvider:
    if settings.WEATHER_MOCK_MODE:
        return MockWeatherProvider()
    return LiveWeatherProvider()


def assess_flight_conditions(lat: float, lon: float) -> WeatherAssessment:
    """Fetch current conditions and evaluate them against safe-flight thresholds."""
    provider = get_weather_provider()
    snapshot = provider.get_current_conditions(lat, lon)
    warnings: list[str] = []

    if snapshot.wind_speed_mps > MAX_SAFE_WIND_MPS:
        warnings.append(
            f"Sustained wind {snapshot.wind_speed_mps:.1f} m/s exceeds safe threshold "
            f"({MAX_SAFE_WIND_MPS:.1f} m/s)."
        )
    if snapshot.wind_gust_mps > MAX_SAFE_GUST_MPS:
        warnings.append(
            f"Wind gusts {snapshot.wind_gust_mps:.1f} m/s exceed safe threshold "
            f"({MAX_SAFE_GUST_MPS:.1f} m/s)."
        )
    if snapshot.precipitation_mm_hr > MAX_SAFE_PRECIP_MM_HR:
        warnings.append(
            f"Precipitation {snapshot.precipitation_mm_hr:.1f} mm/hr exceeds safe threshold "
            f"({MAX_SAFE_PRECIP_MM_HR:.1f} mm/hr)."
        )
    if snapshot.visibility_km < MIN_SAFE_VISIBILITY_KM:
        warnings.append(
            f"Visibility {snapshot.visibility_km:.1f} km is below the safe minimum "
            f"({MIN_SAFE_VISIBILITY_KM:.1f} km)."
        )

    return WeatherAssessment(snapshot=snapshot, is_flight_safe=len(warnings) == 0, warnings=warnings)
