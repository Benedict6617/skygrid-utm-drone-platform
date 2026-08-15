"""
SQLAlchemy engine/session management.

Uses SQLite by default for zero-config local development and demos.
Point DATABASE_URL at PostgreSQL for production deployments — the
ORM layer is database-agnostic.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(settings.DATABASE_URL, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)

Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a request-scoped DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables. Called on startup and by scripts/seed_data.py."""
    from app.models import (  # noqa: F401  (import registers models with Base)
        operator,
        drone,
        flight_plan,
        geofence,
        airspace,
        landing_zone,
        telemetry,
        weather,
        atc_event,
    )

    Base.metadata.create_all(bind=engine)
