"""FastAPI entrypoint for the empathetic routing website."""

from typing import Any

import requests
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.ai.gemini import get_gemini_weights
from backend.config import get_settings
from backend.routing.routing import RouteRequestData, recommend_routes
from backend.weather.weather_api import fetch_weather_snapshot


class RecommendRequest(BaseModel):
    """Request body for /recommend."""

    origin: str
    destination: str
    gender: str
    age: int = Field(ge=0, le=120)
    weight: float = Field(default=60.0, gt=0, le=300)
    vehicles: list[str] = Field(default_factory=list)
    complaint: str = ""


class RecommendResponse(BaseModel):
    """Response body for /recommend."""

    reasoning: str
    routes: list[dict[str, Any]]
    ai: dict[str, Any]
    weather: dict[str, Any]


class GeocodeCandidate(BaseModel):
    """A Taipei-only address search candidate."""

    label: str
    lat: float
    lon: float
    value: str


settings = get_settings()
app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=settings.frontend_dir), name="static")


@app.get("/")
def index() -> FileResponse:
    """Serve the Leaflet frontend."""
    return FileResponse(settings.frontend_dir / "index.html")


@app.get("/geocode", response_model=list[GeocodeCandidate])
def geocode(q: str = Query(min_length=1, max_length=120)) -> list[GeocodeCandidate]:
    """Search an address and keep only results inside Taipei City bounds."""
    query = q if "台北" in q or "臺北" in q else f"台北市 {q}"
    params = {"q": query, "format": "json", "limit": 5, "accept-language": "zh-TW"}
    headers = {"User-Agent": "empathetic-route-recommendation/1.0"}
    try:
        response = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params=params,
            headers=headers,
            timeout=8,
        )
        records = response.json() if response.status_code == 200 else []
    except Exception:
        return []
    return [candidate for record in records if (candidate := geocode_candidate(record))]


@app.post("/recommend", response_model=RecommendResponse)
def recommend(request: RecommendRequest) -> RecommendResponse:
    """Recommend routes using Gemini weights and NetworkX pathfinding."""
    weather = fetch_weather_snapshot()
    ai_result = get_gemini_weights(
        request.complaint,
        build_weather_text(weather),
        build_profile(request),
    )
    route_data = RouteRequestData(
        origin=request.origin,
        destination=request.destination,
        gender=request.gender,
        age=request.age,
        weight=request.weight,
        vehicles=request.vehicles,
        ai_result=ai_result,
        weather=weather,
    )
    return RecommendResponse(
        reasoning=ai_result.get("reasoning", ""),
        routes=recommend_routes(route_data),
        ai=ai_result,
        weather=weather.__dict__,
    )


def build_profile(request: RecommendRequest) -> str:
    """Build profile text for Gemini."""
    return f"{request.gender}, {request.age}歲, {request.weight}kg"


def build_weather_text(weather: object) -> str:
    """Build weather text for Gemini."""
    values = weather.__dict__
    return (
        f"天氣={values.get('weather_desc') or '未知'}, "
        f"降雨={values.get('rain_24h')}, AQI={values.get('aqi')}, "
        f"警報={values.get('extreme_weather_alert')}"
    )


def geocode_candidate(record: dict[str, Any]) -> GeocodeCandidate | None:
    """Convert a Nominatim record into a Taipei-only candidate."""
    try:
        lat = float(record["lat"])
        lon = float(record["lon"])
    except (KeyError, TypeError, ValueError):
        return None
    if not is_inside_taipei_bounds(lat, lon):
        return None
    label = record.get("display_name", "台北市地址")
    return GeocodeCandidate(label=label, lat=lat, lon=lon, value=f"{lat:.6f},{lon:.6f}")


def is_inside_taipei_bounds(lat: float, lon: float) -> bool:
    """Approximate Taipei City bounds shared with the frontend map mask."""
    return 24.95 <= lat <= 25.22 and 121.45 <= lon <= 121.67
