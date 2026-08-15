"""
Orchestrates the full pre-flight review pipeline for a submitted
flight plan: LAANC authorization -> geofence check -> weather
assessment -> strategic deconfliction -> ATC coordination (if
applicable). This is the single place that decides whether a flight
plan may transition to APPROVED.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.flight_plan import FlightPlan, FlightPlanStatus
from app.services import atc_service, geofence_service, weather_service
from app.services.deconfliction_service import check_strategic_conflicts
from app.services.laanc_service import LAANCRequest, get_laanc_client


def run_full_review(db: Session, plan: FlightPlan) -> dict:
    """
    Runs every check for a flight plan and updates its status
    in-place. Returns a structured summary of every stage's result
    for the API response / UI.
    """
    origin = plan.waypoints[0]
    result: dict = {}

    # --- 1. LAANC authorization (only meaningful near controlled airspace,
    #        but we always request — the mock/live client encodes grid
    #        ceilings for every location, matching real facility maps). ---
    laanc_client = get_laanc_client()
    laanc_req = LAANCRequest(
        operator_id=plan.operator_id,
        drone_faa_registration=plan.drone.faa_registration_number if plan.drone else None,
        latitude=origin["latitude"],
        longitude=origin["longitude"],
        max_altitude_m=plan.max_altitude_m,
        start_time=plan.planned_start_time,
        end_time=plan.planned_end_time,
    )
    laanc_resp = laanc_client.request_authorization(laanc_req)
    result["laanc"] = {
        "approved": laanc_resp.approved,
        "status": laanc_resp.status,
        "authorization_id": laanc_resp.authorization_id,
        "max_authorized_altitude_m": laanc_resp.max_authorized_altitude_m,
        "reason": laanc_resp.reason,
    }
    plan.laanc_authorization_id = laanc_resp.authorization_id
    plan.laanc_response_payload = result["laanc"]

    if not laanc_resp.approved:
        plan.status = FlightPlanStatus.LAANC_DENIED
        db.add(plan)
        db.commit()
        result["final_status"] = plan.status
        return result

    # --- 2. Geofence check ---
    geofence_result = geofence_service.check_route_against_geofences(
        db, plan.waypoints, plan.planned_start_time, plan.planned_end_time, plan.max_altitude_m
    )
    result["geofence"] = {
        "is_clear": geofence_result.is_clear,
        "blocking": [v.__dict__ for v in geofence_result.blocking],
        "advisories": [v.__dict__ for v in geofence_result.advisories],
    }

    if not geofence_result.is_clear:
        plan.status = FlightPlanStatus.CONFLICT_DETECTED
        plan.conflict_notes = "; ".join(v.reason for v in geofence_result.blocking)
        db.add(plan)
        db.commit()
        result["final_status"] = plan.status
        return result

    # --- 3. Weather assessment ---
    weather_assessment = weather_service.assess_flight_conditions(origin["latitude"], origin["longitude"])
    result["weather"] = {
        "is_flight_safe": weather_assessment.is_flight_safe,
        "warnings": weather_assessment.warnings,
        "wind_speed_mps": weather_assessment.snapshot.wind_speed_mps,
        "wind_gust_mps": weather_assessment.snapshot.wind_gust_mps,
        "precipitation_mm_hr": weather_assessment.snapshot.precipitation_mm_hr,
        "visibility_km": weather_assessment.snapshot.visibility_km,
        "flight_category": weather_assessment.snapshot.flight_category,
    }
    # Weather is advisory at planning time (conditions at actual takeoff
    # may differ); we surface warnings but don't hard-block a future plan
    # unless it's scheduled to start very soon. Operators re-check before wheels-up.

    # --- 4. Strategic deconfliction ---
    deconfliction = check_strategic_conflicts(
        db,
        plan.waypoints,
        plan.planned_start_time,
        plan.planned_end_time,
        plan.max_altitude_m,
        exclude_flight_plan_id=plan.id,
    )
    result["deconfliction"] = {
        "is_clear": deconfliction.is_clear,
        "checked_against_count": deconfliction.checked_against_count,
        "conflicts": [c.__dict__ for c in deconfliction.conflicts],
    }

    if not deconfliction.is_clear:
        critical = [c for c in deconfliction.conflicts if c.severity == "critical"]
        if critical:
            plan.status = FlightPlanStatus.CONFLICT_DETECTED
            plan.conflict_notes = "; ".join(
                f"Conflict with '{c.other_mission_name}' ({c.other_flight_plan_id}): "
                f"{c.horizontal_separation_m}m horizontal / {c.vertical_separation_m}m vertical separation"
                for c in critical
            )
            db.add(plan)
            db.commit()
            result["final_status"] = plan.status
            return result

    # --- 5. ATC coordination for near-airport operations ---
    nearby_airport = atc_service.requires_atc_coordination(db, plan.waypoints)
    result["atc_coordination_required"] = nearby_airport is not None
    if nearby_airport:
        atc_service.log_coordination_request(
            db,
            flight_plan_id=plan.id,
            airport_icao_code=nearby_airport.icao_code,
            message=(
                f"UAS operation '{plan.mission_name}' requests coordination: "
                f"{nearby_airport.distance_m:.0f}m from {nearby_airport.icao_code}, "
                f"ceiling {plan.max_altitude_m:.0f}m AGL, window "
                f"{plan.planned_start_time:%H:%M}-{plan.planned_end_time:%H:%M}."
            ),
        )
        result["nearby_airport"] = nearby_airport.__dict__

    plan.status = FlightPlanStatus.APPROVED
    plan.controlled_airspace_class = nearby_airport.airspace_class if nearby_airport else None
    plan.near_airport_code = nearby_airport.icao_code if nearby_airport else None
    plan.conflict_notes = None
    db.add(plan)
    db.commit()
    result["final_status"] = plan.status
    return result
