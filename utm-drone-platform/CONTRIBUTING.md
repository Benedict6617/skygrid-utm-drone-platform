# Contributing

Thanks for considering a contribution to SkyGrid UTM.

## Development setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
pytest
uvicorn app.main:app --reload
```

## Code organization

Business logic belongs in `app/services/`, not in routers. Routers should stay thin: validate input via the Pydantic schema, call a service function, shape the response. This keeps the deconfliction/geofencing/LAANC logic unit-testable without spinning up the HTTP layer.

## Adding a new external integration

Follow the existing pattern in `app/services/laanc_service.py` and `app/services/weather_service.py`:

1. Define an abstract base class describing the interface.
2. Implement a `Mock*` class with realistic, deterministic simulated behavior (seed randomness from stable input like location/time so results are reproducible in tests and demos).
3. Implement a `Live*` class that calls the real API.
4. Add a `get_*_client()` / `get_*_provider()` factory function that switches between them based on a settings flag.

## Tests

Run the full suite with `pytest`. New service logic should have unit tests that don't require the HTTP layer (see `tests/test_deconfliction_service.py` for the pattern); new endpoints should have at least one integration test in `tests/test_api_integration.py`.

## Database migrations

This project ships with `Base.metadata.create_all()` for simplicity in development and demos. For schema changes in a real deployment, introduce Alembic migrations (the dependency is already in `requirements.txt`) rather than relying on `create_all`, which won't handle altering existing tables.

## Reporting issues

Please include: the endpoint or service function involved, the request payload (with any credentials redacted), and the full error response or traceback.
