# API Reference

Full interactive documentation (Swagger UI) is always available at `/docs` when the server is running, and the raw OpenAPI schema at `/openapi.json`. This document is a narrative companion covering the endpoints grouped by workflow, with the details that matter for integration that don't always come through in auto-generated docs.

Base path for all endpoints below: `/api/v1`

## Authentication

All endpoints except registration, login, health checks, weather, and read-only geofence/airport listing require a Bearer JWT obtained from `/auth/login`.

| Method | Path | Description |
|---|---|---|
| POST | `/auth/register` | Create an operator account. |
| POST | `/auth/login` | Exchange email + password for a JWT access token (`Authorization: Bearer <token>`). |

Tokens expire after `ACCESS_TOKEN_EXPIRE_MINUTES` (default 60). There is no refresh-token flow in this version — re-authenticate with `/auth/login` once expired.

## Drones

| Method | Path | Description |
|---|---|---|
| POST | `/drones` | Register a drone to the authenticated operator's fleet. |
| GET | `/drones` | List the authenticated operator's drones. |
| GET | `/drones/{drone_id}` | Get a single drone. |
| PATCH | `/drones/{drone_id}/status` | Update operational status (`grounded`, `armed`, `airborne`, `returning`, `emergency`, `maintenance`). |

## Flight plans

| Method | Path | Description |
|---|---|---|
| POST | `/flight-plans` | Create a draft flight plan (route, time window, altitude, priority). |
| POST | `/flight-plans/{id}/submit-for-review` | Runs the full review pipeline: LAANC → geofence → weather → deconfliction → ATC coordination. Returns a structured breakdown of every stage. |
| POST | `/flight-plans/{id}/activate` | Transition an `APPROVED` plan to `ACTIVE` (i.e. the drone has taken off). |
| POST | `/flight-plans/{id}/complete` | Mark an `ACTIVE` plan `COMPLETED`. |
| POST | `/flight-plans/{id}/cancel` | Cancel a plan that hasn't completed. |
| GET | `/flight-plans` | List the authenticated operator's flight plans. |
| GET | `/flight-plans/{id}` | Get a single flight plan. |
| GET | `/flight-plans/active/all` | **Airspace-wide** view of every `ACTIVE` flight plan across all operators — used for shared situational awareness / a live map, not scoped to one operator, since safe deconfliction requires visibility into other traffic. |

### Flight plan status values

`draft` → `pending_laanc` → `laanc_approved` | `laanc_denied` → `pending_deconfliction` → `conflict_detected` | `approved` → `active` → `completed` | `aborted` | `cancelled`

In the current implementation `submit-for-review` runs all pipeline stages synchronously and lands directly on a terminal-for-that-attempt status (`laanc_denied`, `conflict_detected`, or `approved`) rather than pausing at each intermediate status — those intermediate enum values are reserved for a future asynchronous/webhook-driven review flow (e.g. when a LAANC "further coordination required" response needs a human in the loop).

### Submitting a flight plan for review — response shape

```json
{
  "laanc": {
    "approved": true,
    "status": "approved",
    "authorization_id": "LAANC-84213097",
    "max_authorized_altitude_m": 91,
    "reason": null
  },
  "geofence": {
    "is_clear": true,
    "blocking": [],
    "advisories": []
  },
  "weather": {
    "is_flight_safe": true,
    "warnings": [],
    "wind_speed_mps": 4.2,
    "wind_gust_mps": 6.1,
    "precipitation_mm_hr": 0.0,
    "visibility_km": 14.0,
    "flight_category": "VFR"
  },
  "deconfliction": {
    "is_clear": true,
    "checked_against_count": 3,
    "conflicts": []
  },
  "atc_coordination_required": false,
  "final_status": "approved"
}
```

If any blocking stage fails (LAANC denial, blocking geofence, or a critical deconfliction conflict), the response stops at that stage — later stages are not evaluated — and `final_status` reflects the terminal status for that attempt.

## Geofences

| Method | Path | Description |
|---|---|---|
| POST | `/geofences` | Create a geofence from an arbitrary polygon (`[[lon, lat], ...]`, ≥3 points). |
| POST | `/geofences/circle` | Convenience endpoint: create a circular geofence from a center point + radius (tessellated server-side into a polygon). |
| GET | `/geofences` | List all active geofences. |
| GET | `/geofences/{id}` | Get a single geofence. |
| DELETE | `/geofences/{id}` | Deactivate a geofence (soft delete — sets `is_active=false`, doesn't remove history). |

## Telemetry & detect-and-avoid

| Method | Path | Description |
|---|---|---|
| POST | `/telemetry/ingest` | Submit a live position/state report, optionally including DAA sensor contacts. Evaluates tactical risk and emergency trigger conditions in one pass; returns alerts and a recommended action. Intended to be called every 1-2 seconds by an airborne drone's flight controller. |
| GET | `/telemetry/{drone_id}/history` | Retrieve recent telemetry history for a drone. |

### Telemetry ingest — recommended actions

- `continue` — nominal, no action needed.
- `monitor` — an advisory-level DAA contact was detected; no maneuver needed yet.
- `maneuver_to_avoid` — a critical DAA contact requires an avoidance maneuver.
- `divert_to_emergency_landing_zone` — battery critical, link lost, or a critical DAA event triggered an automatic diversion; response includes `nearest_landing_zone_id`.

## Weather

| Method | Path | Description |
|---|---|---|
| GET | `/weather/conditions?latitude=&longitude=` | Current conditions at a location plus a go/no-go safety assessment against configurable wind/gust/precipitation/visibility thresholds. |

## Emergency landing zones

| Method | Path | Description |
|---|---|---|
| GET | `/emergency/landing-zones` | List all landing zones and their availability. |
| GET | `/emergency/landing-zones/nearest?latitude=&longitude=` | Get the best available zone for a given position (used internally by telemetry ingest; also exposed directly for dashboards/testing). |
| PATCH | `/emergency/landing-zones/{id}/availability` | Mark a zone available/unavailable (e.g. while occupied or under maintenance). |

## ATC coordination

| Method | Path | Description |
|---|---|---|
| GET | `/atc/airports` | List reference airport data. |
| GET | `/atc/airports/nearby?latitude=&longitude=&radius_m=` | Find airports within a coordination radius of a point (default 9,260m / 5nm). |
| GET | `/atc/coordination-events/{flight_plan_id}` | Full coordination message log for a flight plan. |

## Error responses

Standard FastAPI/Pydantic validation errors return `422` with a `detail` array describing the invalid fields. Domain errors (not found, unauthorized, invalid state transition) return `404`/`401`/`403`/`400` with a `{"detail": "human-readable message"}` body.
