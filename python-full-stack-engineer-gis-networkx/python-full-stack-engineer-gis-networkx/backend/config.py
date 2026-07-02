"""Application configuration."""

from functools import lru_cache
from pathlib import Path
import os


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings:
    """Runtime settings loaded from environment variables."""

    app_name: str = "Empathetic Route Recommendation"
    frontend_dir: Path = BASE_DIR / "frontend"
    data_dir: Path = BASE_DIR / "data"
    graph_cache_dir: Path = BASE_DIR / "data" / "graphs"
    gemini_api_key: str | None = os.getenv("GEMINI_API_KEY")
    cwa_api_key: str | None = os.getenv("CWA_API_KEY")
    moenv_api_key: str | None = os.getenv("MOENV_API_KEY")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
    taipei_center: tuple[float, float] = (25.040, 121.540)
    search_dist_m: int = 15000
    default_travel_period: str = os.getenv("TRAVEL_PERIOD", "尖峰")
    allow_osm_download: bool = os.getenv("ALLOW_OSM_DOWNLOAD", "false").lower() == "true"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings."""
    settings = Settings()
    settings.graph_cache_dir.mkdir(parents=True, exist_ok=True)
    return settings
