"""
Centralized application configuration.

All values are loaded from environment variables (see .env.example).
Never commit a real .env file — copy .env.example to .env and fill in
real credentials for LAANC, weather, and ATC integrations before
deploying to production.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Application
    APP_NAME: str = "SkyGrid UTM"
    APP_ENV: str = "development"
    DEBUG: bool = True
    SECRET_KEY: str = "insecure-dev-key-change-me"
    API_V1_PREFIX: str = "/api/v1"

    # Database
    DATABASE_URL: str = "sqlite:///./skygrid_utm.db"

    # FAA LAANC
    LAANC_API_BASE_URL: str = "https://api.laanc-sandbox.example.gov"
    LAANC_CLIENT_ID: str = ""
    LAANC_CLIENT_SECRET: str = ""
    LAANC_USS_NAME: str = "SkyGrid UTM Services"
    LAANC_MOCK_MODE: bool = True

    # Weather
    WEATHER_API_BASE_URL: str = "https://api.weather.gov"
    WEATHER_API_KEY: str = ""
    WEATHER_MOCK_MODE: bool = True

    # ATC coordination
    ATC_FACILITY_FEED_URL: str = "https://atc-coordination.example.gov/feed"
    ATC_MOCK_MODE: bool = True

    # Deconfliction thresholds
    MIN_HORIZONTAL_SEPARATION_M: float = 50.0
    MIN_VERTICAL_SEPARATION_M: float = 15.0
    LOOKAHEAD_WINDOW_SECONDS: int = 300

    # Auth
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    ALGORITHM: str = "HS256"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
