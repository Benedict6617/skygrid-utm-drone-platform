# Architecture

## Overview

SkyGrid UTM is a synchronous REST API (FastAPI) backed by a relational database (SQLite for development, PostgreSQL-ready for production) with a clean service-layer separation between:

- **Routers** (`app/routers/`) — HTTP concerns only: request validation, auth, calling services, shaping responses.
- **Services** (`app/services/`) — all business logic. Every external integration (LAANC, weather, ATC) is defined as an abstract interface with a mock and a live implementation, selected by an environment flag.
- **Models** (`app/models/`) — SQLAlchemy ORM tables.
- **Schemas** (`app/schemas/`) — Pydantic request/response contracts, decoupled from ORM models so the API surface can evolve independently of storage.

## The flight plan lifecycle

```
DRAFT
  │  (operator submits for review)
  ▼
run_full_review()  [app/services/flight_review_service.py]
  │
  ├─ 1. LAANC authorization request
  │      → LAANC_DENIED (terminal-ish; can be resubmitted after adjusting plan)
  │
  ├─ 2. Geofence intersection check (space + altitude + time)
  │      → CONFLICT_DETECTED
  │
  ├─ 3. Weather assessment (advisory — surfaced, doesn't hard-block a future-dated plan)
  │
  ├─ 4. Strategic deconfliction against all APPROVED/ACTIVE flight plans
  │      → CONFLICT_DETECTED (only for "critical" severity conflicts;
  │                            "warning" severity is surfaced but doesn't block)
  │
  └─ 5. ATC coordination check (logs a coordination event if near a towered airport)
         ▼
      APPROVED
         │ (operator activates at takeoff)
         ▼
      ACTIVE ──── (continuous telemetry ingest evaluates tactical risk) ────┐
         │                                                                    │
         │ (mission complete)                                    (emergency trigger)
         ▼                                                                    ▼
      COMPLETED                                          drone diverted to nearest
                                                           available emergency landing zone
```

A plan that lands in `CONFLICT_DETECTED` or `LAANC_DENIED` can be edited and resubmitted — `run_full_review` is idempotent and safe to call repeatedly.

## Strategic vs. tactical deconfliction

Real UTM systems separate deconfliction into two layers, and so does this platform:

**Strategic deconfliction** (`check_strategic_conflicts` in `deconfliction_service.py`) runs once, at flight-plan submission time, before any aircraft is airborne. It compares the full planned route of the candidate flight against every other flight plan already in `APPROVED`/`ACTIVE`/`LAANC_APPROVED` status, checking for:

1. **Time window overlap** — do the two flights' planned start/end times overlap at all?
2. **Altitude band overlap** — could the two aircraft occupy the same altitude range? (Currently modeled as both starting from the surface, since small UAS climb from 0 AGL; the hook is in place for non-zero altitude floors later, e.g. dedicated package hand-off corridors.)
3. **Horizontal separation** — the minimum distance between the two routes' line segments, sampled at fixed resolution (`segment_min_distance_m` in `utils/geo.py`), compared against `MIN_HORIZONTAL_SEPARATION_M`.

A conflict is `critical` (blocks approval) if the minimum separation is less than half the required minimum; otherwise it's a `warning` (surfaced to the operator but doesn't block approval — useful for near-miss awareness without over-restricting a small, low-density airspace).

**Tactical deconfliction** (`evaluate_tactical_risk`) runs continuously against live telemetry once a flight is airborne. Each telemetry frame can include a list of detect-and-avoid (DAA) sensor contacts — nearby aircraft, birds, or obstacles detected by onboard sensors (radar, ADS-B receiver, EO/IR camera, or acoustic array, depending on the airframe). The engine estimates time-to-closest-approach from distance and closure rate and issues graduated alerts:

- **Critical** (time-to-closest-approach < 10s and within minimum separation): recommend an immediate avoidance maneuver or emergency landing.
- **Warning**: same proximity threshold, more time to react.
- **Advisory**: contact detected within 2x the minimum separation and closing — monitor.

This mirrors (in simplified form) the well-clear geometry approach used in real DAA systems like DAIDALUS, scaled down for small-UAS operating envelopes rather than manned aircraft.

## Emergency landing zone selection

`select_emergency_landing_zone` (`emergency_service.py`) is triggered automatically by the telemetry ingest endpoint when any of these conditions are met:

- Battery at or below `BATTERY_CRITICAL_PERCENT` (default 15%)
- Command-and-control link quality at or below `LINK_LOSS_THRESHOLD_PERCENT` (default 20%)
- A `critical` tactical DAA alert

Zone selection isn't purely nearest-first: it scores each available zone by `distance × population_density_penalty`, so a slightly farther open field is preferred over a slightly closer parking lot in a dense area, when the difference is meaningful. This reflects real emergency-landing site selection, which prioritizes minimizing risk to people on the ground over minimizing flight time.

## Dynamic geofencing

Geofences are stored as GeoJSON-style polygons (`[[lon, lat], ...]`) with a floor/ceiling altitude and an effective time window (`effective_start` / `effective_end`, where `null` end means indefinite — used for permanent restrictions). A convenience endpoint (`POST /geofences/circle`) accepts a center point + radius and tessellates it into a 32-point polygon (`circle_to_polygon` in `utils/geo.py`), since most real-world TFRs (stadium events, wildfire response areas) are naturally circular.

Route checking samples each waypoint plus the midpoint between consecutive waypoints and tests each sample point against every active geofence's polygon using a standard ray-casting point-in-polygon algorithm. This is a deliberate simplification versus full polygon-polygon intersection (e.g. via Shapely) — it's fast, dependency-light, and sufficiently precise for typical small-UAS route segment lengths (under a few km); a production system flying long linear infrastructure-inspection routes might upgrade to true segment-polygon intersection.

## FAA LAANC integration model

There is no single public FAA LAANC API that all operators call directly — in practice, a UTM platform integrates as a USS (UAS Service Supplier) through one of the FAA's approved industry partners, under a Data Exchange Agreement. `app/services/laanc_service.py` reflects this:

- `LAANCClient` — the abstract interface any real integration implements.
- `MockLAANCClient` — a deterministic simulator (hash-seeded by location + time, so the same request always produces the same simulated outcome) that mimics real LAANC facility-map behavior: each location has a simulated pre-authorized altitude ceiling; requests at or below it are auto-approved, requests above it usually require further coordination.
- `LiveLAANCClient` — a skeleton HTTP client ready to be pointed at a real USS partner API once you have credentials.

The same pattern is used for weather (`weather_service.py`) and ATC coordination (`atc_service.py`): mock and live implementations behind one interface, toggled by an environment flag, so the rest of the codebase never needs to know which one is active.

## Data model summary

| Table | Purpose |
|---|---|
| `operators` | Registered businesses/remote pilots using the platform |
| `drones` | Individual aircraft in an operator's fleet |
| `flight_plans` | Submitted operations: route, time window, status, LAANC/deconfliction results |
| `geofences` | Active restrictions (TFRs, permanent, operator-defined) |
| `airports` | Reference data for ATC-coordination-radius checks |
| `landing_zones` | Pre-surveyed emergency landing sites |
| `telemetry_points` | Live position/state reports, including DAA sensor contacts |
| `weather_observations` | Reserved for caching weather snapshots (not yet wired into a persistence path — currently weather is fetched live per request) |
| `atc_coordination_events` | Log of coordination messages exchanged with towered-airport ATC |

## Scaling considerations

The current implementation is synchronous and single-process, appropriate for a small operator (a few dozen drones, low hundreds of flight plans per day). Scaling further would mean:

- Moving telemetry ingest to an async queue (Kafka/Redis Streams) so tactical deconfliction doesn't block on the HTTP request/response cycle.
- Spatial-indexing geofences and flight plans (e.g. PostGIS) instead of the current linear scan, once the number of concurrent active flight plans grows past a few hundred.
- Splitting the deconfliction service into its own worker process that all API instances publish flight-plan changes to, rather than each request recomputing conflicts against the full active-plan table.
