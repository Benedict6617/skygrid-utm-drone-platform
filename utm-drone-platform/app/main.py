"""
SkyGrid UTM — Unmanned Aircraft System Traffic Management platform.

Entry point that wires together all routers and runs startup tasks
(table creation). See README.md for setup, and docs/ARCHITECTURE.md
for a system overview.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.routers import atc, auth, drones, emergency, flight_plans, geofences, telemetry, weather

app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "UTM platform for coordinating commercial drone delivery, inspection, and "
        "surveillance operations in shared low-altitude airspace: LAANC authorization, "
        "dynamic geofencing, real-time flight path deconfliction, weather-aware go/no-go "
        "checks, detect-and-avoid alerting, emergency landing zone assignment, and "
        "traditional ATC coordination near airports."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.APP_ENV == "development" else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/", tags=["Health"])
def root():
    return {
        "service": settings.APP_NAME,
        "status": "operational",
        "environment": settings.APP_ENV,
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok"}


app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(drones.router, prefix=settings.API_V1_PREFIX)
app.include_router(flight_plans.router, prefix=settings.API_V1_PREFIX)
app.include_router(geofences.router, prefix=settings.API_V1_PREFIX)
app.include_router(telemetry.router, prefix=settings.API_V1_PREFIX)
app.include_router(weather.router, prefix=settings.API_V1_PREFIX)
app.include_router(emergency.router, prefix=settings.API_V1_PREFIX)
app.include_router(atc.router, prefix=settings.API_V1_PREFIX)
