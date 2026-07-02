"""FastAPI entrypoint for the empathetic routing website."""

from typing import Any, List
import requests
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.ai.gemini import get_gemini_weights
from backend.config import get_settings
from backend.models.schemas import (
    RouteRequest,
    RouteResponse,
    StationsResponse,
    WeatherData,
    WeatherDataResponse
)
from backend.routing.routing import RouteRequestData, recommend_routes, parse_place
from backend.api.weather import fetch_district_weather_snapshot
from backend.utils.gis_helper import get_all_stations, get_district_by_coords, get_taipei_boundary_coords

settings = get_settings()
app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static frontend files
app.mount("/static", StaticFiles(directory=str(settings.frontend_dir)), name="static")


@app.on_event("startup")
def startup_event():
    print("=== [Startup] Pre-loading GIS boundaries and Shapefile stations ===")
    # Trigger lazy loaders to populate caches
    get_all_stations()
    get_taipei_boundary_coords()
    get_district_by_coords(25.033, 121.565) # Warm up town cache
    
    print("=== [Startup] Pre-loading OSMnx network graphs (this may take a moment if downloading) ===")
    # Trigger graph load/download
    from backend.api.weather import WeatherSnapshot
    dummy_weather = WeatherSnapshot()
    dummy_data = RouteRequestData(
        origin="25.0478,121.5319",
        destination="25.0478,121.5319",
        gender="男性",
        age=30,
        weight=60.0,
        vehicles=[],
        ai_result={},
        weather=dummy_weather
    )
    from backend.routing.routing import get_prepared_graphs
    get_prepared_graphs(dummy_data)
    print("=== [Startup] Pre-loading complete! FastAPI server is ready ===")


@app.get("/")
def index() -> FileResponse:
    """Serve the Leaflet frontend HTML page."""
    return FileResponse(str(settings.frontend_dir / "index.html"))


@app.get("/geocode", response_model=List[dict])
def geocode(q: str = Query(min_length=1, max_length=120)) -> List[dict]:
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
    except Exception as e:
        print(f"[Error] Geocoding request failed: {e}")
        return []
        
    candidates = []
    for record in records:
        candidate = geocode_candidate(record)
        if candidate:
            candidates.append(candidate)
    return candidates


@app.post("/recommend", response_model=RouteResponse)
def recommend(request: RouteRequest) -> RouteResponse:
    """Recommend unique routes using Gemini weights and NetworkX pathfinding."""
    try:
        # Parse origin and destination to get their lat/lon coordinates
        origin_lat, origin_lon = parse_place(request.origin)
        dest_lat, dest_lon = parse_place(request.destination)
        
        # 1. 空間判定起終點行政區 (鄉鎮市區)
        origin_district = get_district_by_coords(origin_lat, origin_lon)
        dest_district = get_district_by_coords(dest_lat, dest_lon)
        
        # 2. 獨立抓取起訖點兩筆鄉鎮氣象預報資料
        origin_weather = fetch_district_weather_snapshot(origin_district)
        dest_weather = fetch_district_weather_snapshot(dest_district)
        
        # Format weather context string for Gemini with both start/end details
        weather_text = (
            f"起點({origin_district}): 天氣={origin_weather.weather_desc or '未知'}, 溫度={origin_weather.temperature or '未知'}°C, 降雨率={origin_weather.rain_probability or 0.0}%; "
            f"終點({dest_district}): 天氣={dest_weather.weather_desc or '未知'}, 溫度={dest_weather.temperature or '未知'}°C, 降雨率={dest_weather.rain_probability or 0.0}%. "
            f"即時空品AQI={origin_weather.aqi or '未知'}, "
            f"災害天氣警報={origin_weather.extreme_weather_alert}"
        )
        
        # User profile text
        profile_text = f"性別: {request.gender}, 年齡: {request.age}歲, 體重: {request.weight}kg"
        
        # Call Gemini AI
        ai_result = get_gemini_weights(
            request.complaint,
            weather_text,
            profile_text,
        )
        
        # Routing request data using origin weather as wind baseline
        route_data = RouteRequestData(
            origin=request.origin,
            destination=request.destination,
            gender=request.gender,
            age=request.age,
            weight=request.weight,
            vehicles=request.vehicles,
            ai_result=ai_result,
            weather=origin_weather,
        )
        
        # Run unique routing algorithm
        routes = recommend_routes(route_data)
        
        # Format response
        origin_schema = map_weather_schema(origin_weather)
        dest_schema = map_weather_schema(dest_weather)
        
        return RouteResponse(
            reasoning=ai_result.get("reasoning", ""),
            routes=routes,
            ai=ai_result,
            weather=WeatherDataResponse(
                origin=origin_schema,
                destination=dest_schema
            )
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")


@app.get("/api/stations", response_model=StationsResponse)
def get_stations() -> StationsResponse:
    """Return all MRT, Train, and Bus stations from geodata shapefiles."""
    try:
        stations = get_all_stations()
        return StationsResponse(
            mrt=stations.get("mrt", []),
            train=stations.get("train", []),
            bus=stations.get("bus", [])
        )
    except Exception as e:
        print(f"[Error] Error fetching stations: {e}")
        return StationsResponse(mrt=[], train=[], bus=[])


@app.get("/api/taipei-boundary")
def get_taipei_boundary() -> dict:
    """Return simplified Taipei City boundary coordinates for map masking."""
    try:
        return get_taipei_boundary_coords()
    except Exception as e:
        print(f"[Error] Error fetching Taipei boundary: {e}")
        return {"exterior": [], "interiors": []}


def map_weather_schema(w) -> WeatherData:
    """Map WeatherSnapshot model properties to WeatherData schema."""
    return WeatherData(
        district=w.district,
        weather_desc=w.weather_desc,
        rain_24h=w.rain_24h,
        rain_probability=w.rain_probability,
        aqi=w.aqi,
        temperature=w.temperature,
        wind_speed=w.wind_speed,
        extreme_weather_alert=w.extreme_weather_alert,
        heat_warning_level=w.heat_warning_level
    )


def geocode_candidate(record: dict) -> dict | None:
    """Convert a Nominatim record into a candidate coordinate."""
    try:
        lat = float(record["lat"])
        lon = float(record["lon"])
    except (KeyError, TypeError, ValueError):
        return None
        
    # Boundary pre-filter
    if not is_inside_taipei_bounds(lat, lon):
        return None
        
    label = record.get("display_name", "台北市地址")
    return {
        "label": label,
        "lat": lat,
        "lon": lon,
        "value": f"{lat:.6f},{lon:.6f}"
    }


def is_inside_taipei_bounds(lat: float, lon: float) -> bool:
    """Approximate bounding box for geocoding pre-filtering."""
    return 24.95 <= lat <= 25.22 and 121.45 <= lon <= 121.67