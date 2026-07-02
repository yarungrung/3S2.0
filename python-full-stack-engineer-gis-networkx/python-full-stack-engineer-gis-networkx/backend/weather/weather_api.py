"""Weather, AQI, and extreme-weather logic from the notebook."""

from dataclasses import dataclass
import requests

from backend.config import get_settings


@dataclass
class WeatherSnapshot:
    """Current Taipei environmental snapshot."""

    weather_desc: str | None = None
    rain_24h: float | None = None
    rain_probability: float | None = None
    aqi: float | None = None
    temperature: float | None = None
    wind_speed: float | None = None
    extreme_weather_alert: str = "正常"
    heat_warning_level: str | None = None


def fetch_weather_snapshot() -> WeatherSnapshot:
    """Fetch weather and AQI, preserving notebook fallback behavior."""
    snapshot = WeatherSnapshot()
    settings = get_settings()
    if settings.cwa_api_key:
        fetch_cwa_observation(snapshot, settings.cwa_api_key)
        fetch_cwa_forecast(snapshot, settings.cwa_api_key)
    if settings.moenv_api_key:
        fetch_aqi(snapshot, settings.moenv_api_key)
    apply_extreme_weather(snapshot)
    return snapshot


def fetch_cwa_observation(snapshot: WeatherSnapshot, api_key: str) -> None:
    """Fetch CWA station observations used by the notebook."""
    station_ids = "466920,C0A980,C0A9C0,C0A9F0,C0AC70"
    url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/O-A0001-001"
    try:
        res = requests.get(url, params={"Authorization": api_key, "StationId": station_ids}, timeout=12)
        stations = res.json()["records"]["Station"] if res.status_code == 200 else []
        update_observation_from_stations(snapshot, stations)
    except Exception:
        return


def update_observation_from_stations(snapshot: WeatherSnapshot, stations: list[dict]) -> None:
    """Average station values with the same validation rules as the notebook."""
    rains: list[float] = []
    temps: list[float] = []
    winds: list[float] = []
    descriptions: list[str] = []
    for station in stations:
        collect_station_values(station, rains, temps, winds, descriptions)
    if rains:
        snapshot.rain_24h = sum(rains) / len(rains)
    if temps:
        snapshot.temperature = sum(temps) / len(temps)
    if winds:
        snapshot.wind_speed = sum(winds) / len(winds)
    snapshot.weather_desc = descriptions[0] if descriptions else "晴"


def collect_station_values(station: dict, rains: list, temps: list, winds: list, descs: list) -> None:
    """Collect a single CWA station's usable values."""
    element = station.get("WeatherElement", {})
    try:
        rain = float(element["Now"]["Rainfall24hr"])
        rains.append(0.0 if rain in {-998.0, -999.0} else rain)
    except Exception:
        pass
    try:
        temp = float(element["AirTemperature"])
        if -50 <= temp <= 60:
            temps.append(temp)
    except Exception:
        pass
    try:
        wind = float(element["WindSpeed"])
        if wind >= 0:
            winds.append(wind)
    except Exception:
        pass
    weather = element.get("Weather")
    if weather and weather not in {"-99", "-999"}:
        descs.append(weather)


def fetch_cwa_forecast(snapshot: WeatherSnapshot, api_key: str) -> None:
    """Fetch Taipei rain probability from CWA."""
    url = "https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-C0032-001"
    params = {"Authorization": api_key, "locationName": "臺北市", "elementName": "PoP"}
    try:
        res = requests.get(url, params=params, timeout=12)
        data = res.json()
        value = data["records"]["location"][0]["weatherElement"][0]["time"][0]["parameter"]["parameterName"]
        snapshot.rain_probability = float(value)
    except Exception:
        return


def fetch_aqi(snapshot: WeatherSnapshot, api_key: str) -> None:
    """Fetch Taipei AQI from MOENV primary and fallback endpoints."""
    channels = ["aqx_p_432", "aqx_p_434"]
    for channel in channels:
        url = f"https://data.moenv.gov.tw/api/v2/{channel}"
        try:
            res = requests.get(url, params={"language": "zh", "api_key": api_key}, timeout=10)
            records = parse_aqi_records(res.json()) if res.status_code == 200 else []
            values = taipei_aqi_values(records)
            if values:
                snapshot.aqi = sum(values) / len(values)
                return
        except Exception:
            continue


def parse_aqi_records(data: object) -> list[dict]:
    """Handle the notebook's list/dict AQI response compatibility."""
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        return [item for item in data.get("records", []) if isinstance(item, dict)]
    return []


def taipei_aqi_values(records: list[dict]) -> list[float]:
    """Return cleaned Taipei AQI values."""
    values = []
    for record in records:
        county = record.get("county") or record.get("County") or record.get("sitename")
        aqi_value = record.get("aqi") or record.get("AQI")
        if county in {"臺北市", "台北市"} and str(aqi_value).strip() not in {"", "None", "-999"}:
            values.append(float(aqi_value))
    return values


def apply_extreme_weather(snapshot: WeatherSnapshot) -> None:
    """Apply the notebook's heat, rain, and wind alert thresholds."""
    if snapshot.temperature is not None:
        if snapshot.temperature >= 38.0:
            snapshot.heat_warning_level = "紅色燈號（極端高溫）"
        elif snapshot.temperature >= 37.0:
            snapshot.heat_warning_level = "橙色燈號（非常高溫）"
        elif snapshot.temperature >= 36.0:
            snapshot.heat_warning_level = "黃色燈號（高溫提示）"
    if snapshot.rain_24h is not None and snapshot.rain_24h >= 80.0:
        snapshot.extreme_weather_alert = "豪雨特報" if snapshot.rain_24h >= 200.0 else "大雨特報"
    if snapshot.wind_speed is not None and snapshot.wind_speed >= 10.0:
        snapshot.extreme_weather_alert = "陸上強風特報"
