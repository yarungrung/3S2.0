from pydantic import BaseModel, Field
from typing import Any, List, Optional

class RouteRequest(BaseModel):
    origin: str = Field(..., description="Starting location as address or 'lat,lon' coordinates")
    destination: str = Field(..., description="Ending location as address or 'lat,lon' coordinates")
    gender: str = Field(..., description="Biological gender: '男性' or '女性'")
    age: int = Field(..., ge=0, le=120, description="Age of the traveler")
    weight: float = Field(default=60.0, gt=0, le=300, description="Weight of the traveler in kg")
    vehicles: List[str] = Field(default_factory=list, description="List of allowed vehicles")
    complaint: str = Field(default="", description="Natural language complaint describing user preferences")

class RouteItem(BaseModel):
    rank: int
    vehicle: str
    time_seconds: float
    time_minutes: float
    adjusted_time_seconds: float
    fare: float
    distance_meters: float
    coordinates: List[List[float]]
    board_station: Optional[dict] = None
    alight_station: Optional[dict] = None

class WeatherData(BaseModel):
    district: str
    weather_desc: Optional[str] = None
    rain_24h: Optional[float] = None
    rain_probability: Optional[float] = None
    aqi: Optional[float] = None
    temperature: Optional[float] = None
    wind_speed: Optional[float] = None
    extreme_weather_alert: str = "正常"
    heat_warning_level: Optional[str] = None

class WeatherDataResponse(BaseModel):
    origin: WeatherData
    destination: WeatherData

class RouteResponse(BaseModel):
    reasoning: str
    routes: List[RouteItem]
    ai: dict
    weather: WeatherDataResponse

class StationItem(BaseModel):
    name: str
    lat: float
    lon: float

class StationsResponse(BaseModel):
    mrt: List[StationItem]
    train: List[StationItem]
    bus: List[StationItem]
