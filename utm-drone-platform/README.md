# SkyGrid UTM

**An Unmanned Aircraft System Traffic Management (UTM) platform for small drone operations businesses.**

SkyGrid UTM coordinates commercial drone delivery, inspection, surveillance, and mapping operations in shared low-altitude airspace. It handles FAA LAANC authorization, dynamic geofencing, real-time flight path deconfliction, weather-aware go/no-go checks, detect-and-avoid (DAA) alerting, automatic emergency landing zone assignment, and coordination with traditional Air Traffic Control near airports.

Built as a backend API (FastAPI + SQLAlchemy) that a fleet dashboard, mobile ground-control app, or flight-controller integration can sit on top of. Runs out of the box with SQLite and simulated LAANC/weather/ATC integrations, so you can evaluate and demo it with zero external credentials, then swap in live integrations for production.

---

## Why this exists

Small drone operations businesses — a local delivery courier, an infrastructure inspection company, a precision-agriculture mapping outfit — increasingly need the same airspace-safety infrastructure that used to be exclusive to large logistics companies: authorization workflows, conflict detection between their own (and nearby operators') flights, and a documented safety case for emergencies. SkyGrid UTM packages that as a single deployable service instead of a spreadsheet and a group chat.

## Core capabilities

| Capability | What it does |
|---|---|
| **FAA LAANC integration** | Requests airspace authorization per flight plan against simulated (or live) facility-map grid ceilings; records approval/denial and the authorization ID. |
| **Dynamic geofencing** | Define temporary flight restrictions (TFRs), permanent restricted areas, and operator-defined keep-outs as polygons or circles; every flight plan is checked for intersection, altitude, and time-window overlap before approval. |
| **Strategic deconfliction** | Compares a new flight plan's full 4D route (space + altitude + time) against every other approved/active flight plan to catch conflicts before takeoff. |
| **Tactical deconfliction (DAA)** | Evaluates onboard detect-and-avoid sensor contacts streamed with live telemetry and raises graduated alerts (advisory/warning/critical) with recommended maneuvers. |
| **Emergency landing zones** | Automatically selects and diverts a drone to the nearest available pre-surveyed landing zone on battery-critical, lost-link, or critical DAA conditions, weighted by site safety (population density, surface type). |
| **Weather integration** | Pulls current wind/gust/precipitation/visibility conditions per location and issues a go/no-go safety assessment against configurable thresholds. |
| **ATC coordination** | Detects when a route falls within coordination range of a towered airport and logs the coordination exchange. |
| **Fleet & operator management** | Multi-tenant: each operator company manages its own drones and flight plans behind JWT authentication. |

## Architecture at a glance

```
Operator/Dashboard/Flight Controller
              │
              ▼
      FastAPI HTTP API  (app/routers/*)
              │
              ▼
   Service layer (app/services/*)
   ┌─────────────┬─────────────┬───────────────┬───────────────┬───────────────┐
   │ LAANC client │ Geofencing  │ Deconfliction │ Weather       │ ATC / Emergency│
   └─────────────┴─────────────┴───────────────┴───────────────┴───────────────┘
              │
              ▼
    SQLAlchemy ORM → SQLite (dev) / PostgreSQL (prod)
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full design, including the strategic vs. tactical deconfliction model and how mock integrations map to real ones.

## Quick start

### Option A — Docker (recommended)

```bash
cp .env.example .env
docker compose up --build
```

The API is now live at `http://localhost:8000`, with interactive docs at `http://localhost:8000/docs`.

### Option B — Local Python environment

```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env

uvicorn app.main:app --reload
```

### Load realistic sample data

Seeds three sample operator businesses (a delivery courier, an infrastructure inspection company, and a precision-agriculture mapping company), their drone fleets, reference airports, active geofences/TFRs, emergency landing zones, and sample flight plans:

```bash
python -m scripts.seed_data
```

Sample login credentials are listed in [`data/sample_operators.json`](data/sample_operators.json) — for example:

```
email: ops@meridianaerial.example
password: MeridianOps#2026
```

### Run the tests

```bash
pytest
```

## Example workflow

```bash
# 1. Register an operator account
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"company_name":"Acme Drone Delivery","contact_email":"ops@acmedrone.example","password":"SecurePass123"}'

# 2. Log in
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"contact_email":"ops@acmedrone.example","password":"SecurePass123"}'
# -> { "access_token": "...", "token_type": "bearer" }

# 3. Register a drone (use the token from step 2)
curl -X POST http://localhost:8000/api/v1/drones \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"serial_number":"ACME-0001","model":"DeliverX 400","manufacturer":"Skyline Robotics","category":"delivery","max_altitude_m":90}'

# 4. Submit a flight plan and run it through the full review pipeline
curl -X POST http://localhost:8000/api/v1/flight-plans \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{
    "drone_id": "<drone_id>",
    "mission_name": "Downtown Lunch Run",
    "purpose": "delivery",
    "waypoints": [
      {"sequence":1,"latitude":39.96,"longitude":-83.00,"altitude_m":0},
      {"sequence":2,"latitude":39.97,"longitude":-83.01,"altitude_m":80}
    ],
    "planned_start_time": "2026-09-01T14:00:00",
    "planned_end_time": "2026-09-01T14:20:00",
    "max_altitude_m": 90
  }'

curl -X POST http://localhost:8000/api/v1/flight-plans/<plan_id>/submit-for-review \
  -H "Authorization: Bearer <token>"
```

The review response includes the LAANC result, geofence check, weather assessment, deconfliction result, and whether ATC coordination was triggered — everything needed to show an operator (or a regulator) why a flight was approved or denied.

## Configuration

All configuration is via environment variables — see [`.env.example`](.env.example) for the full list. Key toggles:

- `LAANC_MOCK_MODE`, `WEATHER_MOCK_MODE`, `ATC_MOCK_MODE` — set to `false` and supply real credentials to connect live integrations. Each mock implements the same interface as its live counterpart (see `app/services/*_service.py`), so swapping is a one-line change in the `get_*_client()` factory function.
- `MIN_HORIZONTAL_SEPARATION_M` / `MIN_VERTICAL_SEPARATION_M` — separation standards enforced by the deconfliction engine.
- `DATABASE_URL` — defaults to local SQLite; point at PostgreSQL for production.

## Project structure

```
app/
  config.py            Environment-driven settings
  database.py           SQLAlchemy engine/session setup
  main.py                FastAPI app entrypoint
  models/                 SQLAlchemy ORM models
  schemas/                 Pydantic request/response schemas
  services/                 Business logic (LAANC, weather, geofencing, deconfliction, emergency, ATC)
  routers/                   API endpoints
  core/                        Auth (JWT) and security utilities
  utils/                        Geospatial math (haversine, point-in-polygon, etc.)
data/                sample_*.json — realistic seed data
scripts/seed_data.py  Loads sample data into the database
tests/                pytest suite covering services + API integration
docs/                 Architecture and API documentation
```

## Production notes

This repository is a complete, runnable reference implementation, not a toy demo — the deconfliction math, geofence intersection logic, and emergency landing selection are real, tested algorithms, not hardcoded responses. Before operating real aircraft on it, you would still need to:

1. Replace `MockLAANCClient` with a live integration through an FAA-approved USS partner (the FAA does not expose a single public LAANC endpoint directly).
2. Point the weather integration at a licensed aviation-weather provider.
3. Move from SQLite to PostgreSQL and add connection pooling for concurrent flight volume.
4. Add a message queue (e.g. Kafka/Redis Streams) in front of the telemetry ingest endpoint once you're past a few dozen concurrent drones — the current synchronous ingest path is fine for a small fleet but will need to move to async/batched processing at scale.
5. Have your deconfliction separation minimums and DAA alerting logic reviewed against your jurisdiction's operating rules; the defaults here are reasonable starting points, not a certified safety case.

## License

MIT — see [`LICENSE`](LICENSE).
