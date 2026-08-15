from fastapi import APIRouter, Query

from app.services.weather_service import assess_flight_conditions

router = APIRouter(prefix="/weather", tags=["Weather"])


@router.get("/conditions")
def get_conditions(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
):
    """Current conditions + go/no-go safety assessment for a location."""
    assessment = assess_flight_conditions(latitude, longitude)
    return {
        "location": {"latitude": latitude, "longitude": longitude},
        "observed_at": assessment.snapshot.observed_at,
        "source": assessment.snapshot.source,
        "wind_speed_mps": assessment.snapshot.wind_speed_mps,
        "wind_gust_mps": assessment.snapshot.wind_gust_mps,
        "wind_direction_deg": assessment.snapshot.wind_direction_deg,
        "precipitation_mm_hr": assessment.snapshot.precipitation_mm_hr,
        "visibility_km": assessment.snapshot.visibility_km,
        "temperature_c": assessment.snapshot.temperature_c,
        "flight_category": assessment.snapshot.flight_category,
        "is_flight_safe": assessment.is_flight_safe,
        "warnings": assessment.warnings,
    }
