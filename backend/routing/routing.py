"""NetworkX routing engine."""

from dataclasses import dataclass
from typing import Any, List, Dict
import networkx as nx

from backend.config import get_settings
from backend.routing.graph import RoutingGraphs, build_graphs, prepare_graphs, SAFETY_COEFFICIENTS
from backend.api.weather import WeatherSnapshot
from backend.routing.walking_speed import calculate_walk_speed, fare_identity
from backend.routing.fare import mrt_fare, train_fare, bus_fare, taxi_fare, ubike_fare

VEHICLE_MODES = {
    "walking": ("walk", "walk"),
    "walk": ("walk", "walk"),
    "ubike": ("walk", "youbike"),
    "youbike": ("walk", "youbike"),
    "mrt": ("rail", "mrt"),
    "train": ("rail", "train"),
    "bus": ("drive", "bus"),
    "car": ("drive", "car"),
    "scooter": ("drive", "motorcycle"),
    "motorcycle": ("drive", "motorcycle"),
    "taxi": ("drive", "taxi"),
}

@dataclass
class RouteRequestData:
    """Routing data passed from FastAPI into the engine."""
    origin: str
    destination: str
    gender: str
    age: int
    weight: float
    vehicles: List[str]
    ai_result: Dict[str, Any]
    weather: WeatherSnapshot


_GRAPHS: RoutingGraphs | None = None


def recommend_routes(data: RouteRequestData) -> List[Dict[str, Any]]:
    """
    Return the top three NetworkX routes after applying AI weights.
    Ensures that each recommended route is a unique transportation mode (no duplicates).
    """
    graphs = get_prepared_graphs(data)
    candidates_by_mode = []
    
    for vehicle in allowed_vehicles(data):
        routes = route_for_vehicle(graphs, vehicle, data.origin, data.destination, data)
        if routes:
            routes.sort(key=lambda item: item["adjusted_time_seconds"])
            candidates_by_mode.append(routes[0])
            
    candidates_by_mode.sort(key=lambda item: item["adjusted_time_seconds"])
    return candidates_by_mode[:3]


def get_prepared_graphs(data: RouteRequestData) -> RoutingGraphs:
    """Load graphs once, then apply per-request formulas."""
    global _GRAPHS
    if _GRAPHS is None:
        _GRAPHS = build_graphs()
        
    multiplier = float(data.ai_result.get("walking_speed_multiplier", 1.0))
    settings = get_settings()
    
    return prepare_graphs(
        _GRAPHS,
        data.age,
        data.gender,
        data.weight,
        multiplier,
        settings.default_travel_period,
        wind_speed=data.weather.wind_speed or 2.5,
    )


def allowed_vehicles(data: RouteRequestData) -> List[str]:
    """Apply user-selected vehicles and Gemini banned vehicle filtering."""
    requested = data.vehicles or list(VEHICLE_MODES.keys())
    banned = {normalize_vehicle(v) for v in data.ai_result.get("banned_vehicles", [])}
    allowed = []
    for vehicle in requested:
        normalized = normalize_vehicle(vehicle)
        if normalized in VEHICLE_MODES and normalized not in banned:
            allowed.append(normalized)
    return sorted(set(allowed))


def route_for_vehicle(
    graphs: RoutingGraphs,
    vehicle: str,
    origin: str,
    destination: str,
    data: RouteRequestData
) -> List[Dict]:
    """Calculate up to three route paths for one vehicle using pre-built DiGraphs."""
    graph_name, mode = VEHICLE_MODES[vehicle]
    
    # Resolve the pre-built DiGraph key
    di_key = vehicle
    if vehicle in ["mrt", "train"]:
        settings = get_settings()
        period = normalize_period(settings.default_travel_period)
        di_key = f"{vehicle}_{period}"
        
    if not graphs.di_graphs or di_key not in graphs.di_graphs:
        return []
        
    di_graph = graphs.di_graphs[di_key]
    
    # Parse coordinates of exact clicked points
    origin_lat, origin_lon = parse_place(origin)
    dest_lat, dest_lon = parse_place(destination)
    
    source = nearest_node(di_graph, origin)
    target = nearest_node(di_graph, destination)
    
    if source == -1 or target == -1:
        return []
        
    paths = shortest_paths(di_graph, source, target, 3)
    
    weight = mode_weight(vehicle, data.ai_result)
    
    return [
        summarize_path(
            di_graph, path, vehicle, mode, weight, index + 1,
            [origin_lat, origin_lon], [dest_lat, dest_lon], data
        )
        for index, path in enumerate(paths)
    ]


def normalize_vehicle(vehicle: str) -> str:
    """Normalize frontend, Gemini, and notebook vehicle names."""
    mapping = {"walking": "walking", "walk": "walking", "scooter": "scooter", "motorcycle": "scooter"}
    mapping.update({"ubike": "ubike", "youbike": "ubike", "mrt": "mrt", "bus": "bus"})
    mapping.update({"train": "train", "car": "car", "taxi": "taxi"})
    return mapping.get(vehicle.lower(), vehicle.lower())


def mode_weight(vehicle: str, ai: dict[str, Any]) -> float:
    """Return Gemini weight for a vehicle."""
    weights = ai.get("weights", {})
    aliases = {"walking": "walking", "scooter": "scooter", "ubike": "ubike"}
    return float(weights.get(aliases.get(vehicle, vehicle), weights.get(vehicle, 1.0)))


def shortest_paths(graph: nx.DiGraph, source: int, target: int, count: int) -> List[List[int]]:
    """Return up to count shortest simple paths using Yen's algorithm."""
    try:
        generator = nx.shortest_simple_paths(graph, source, target, weight="weight")
        return [path for _, path in zip(range(count), generator)]
    except Exception as e:
        print(f"[Error in shortest_paths] from {source} to {target}: {e}")
        return []


def summarize_path(
    graph: nx.DiGraph,
    path: List[int],
    vehicle: str,
    mode: str,
    weight: float,
    rank: int,
    origin_coords: List[float],
    dest_coords: List[float],
    data: RouteRequestData
) -> dict:
    """
    Summarize travel metrics and geometries along the path.
    Fares are calculated dynamically based on total route distance or time.
    """
    totals = {"time": 0.0, "fare": 0.0, "distance": 0.0, "adjusted": 0.0}
    
    coordinates = [origin_coords]
    
    first_node_coords = [graph.nodes[path[0]]["y"], graph.nodes[path[0]]["x"]]
    if abs(first_node_coords[0] - origin_coords[0]) > 1e-6 or abs(first_node_coords[1] - origin_coords[1]) > 1e-6:
        coordinates.append(first_node_coords)
        
    identity = fare_identity(data.age)
    walk_multiplier = float(data.ai_result.get("walking_speed_multiplier", 1.0))
    walk_speed = calculate_walk_speed(data.age, data.gender) * walk_multiplier
    
    safety_coef = SAFETY_COEFFICIENTS.get(mode, 1.0)
    
    for u, v in zip(path[:-1], path[1:]):
        edge_data = graph[u][v]
        length_m = edge_data["length"]
        base_time = edge_data["pure_time"]
        safety_val = edge_data["safety_cost"] * safety_coef
        
        # Calculate dynamic travel time for walk based on user demographics
        if mode == "walk":
            pure_time = seconds_by_speed(length_m, walk_speed)
        else:
            pure_time = base_time
            
        totals["time"] += pure_time
        totals["distance"] += length_m
        totals["adjusted"] += pure_time * weight * (1.0 + safety_val)
        coordinates.append([graph.nodes[v]["y"], graph.nodes[v]["x"]])
        
    last_node_coords = coordinates[-1]
    if abs(last_node_coords[0] - dest_coords[0]) > 1e-6 or abs(last_node_coords[1] - dest_coords[1]) > 1e-6:
        coordinates.append(dest_coords)
        
    # Calculate fares dynamically for the whole route
    total_dist_km = totals["distance"] / 1000.0
    if vehicle == "walking":
        totals["fare"] = 0.0
    elif vehicle == "ubike":
        totals["fare"] = ubike_fare(totals["time"] / 60.0, identity)
    elif vehicle == "mrt":
        totals["fare"] = mrt_fare(total_dist_km, identity)
    elif vehicle == "train":
        totals["fare"] = train_fare(total_dist_km, identity)
    elif vehicle == "bus":
        totals["fare"] = bus_fare(identity)
    elif vehicle == "taxi":
        totals["fare"] = taxi_fare(total_dist_km)
    elif vehicle == "car":
        totals["fare"] = total_dist_km * 3.5
    elif vehicle == "scooter":
        totals["fare"] = total_dist_km * 0.8
        
    # Find boarding and alighting stations for transit modes
    board_st = None
    alight_st = None
    if vehicle in ["mrt", "train", "bus"]:
        from backend.utils.gis_helper import find_nearest_station
        board_st = find_nearest_station(first_node_coords[0], first_node_coords[1], vehicle)
        alight_st = find_nearest_station(last_node_coords[0], last_node_coords[1], vehicle)
        
    payload = route_payload(rank, vehicle, totals, coordinates)
    payload["board_station"] = board_st
    payload["alight_station"] = alight_st
    return payload


def route_payload(rank: int, vehicle: str, totals: dict[str, float], coordinates: List[List[float]]) -> dict:
    """Build API route payload."""
    return {
        "rank": rank,
        "vehicle": vehicle,
        "time_seconds": round(totals["time"], 2),
        "time_minutes": round(totals["time"] / 60.0, 1),
        "adjusted_time_seconds": round(totals["adjusted"], 2),
        "fare": round(totals["fare"], 1),
        "distance_meters": round(totals["distance"], 1),
        "coordinates": coordinates,
    }


def nearest_node(graph: nx.DiGraph, place: str) -> int:
    """Find nearest graph node from 'lat,lon' or a geocoded place string."""
    if not graph or graph.number_of_nodes() == 0:
        return -1
    lat, lon = parse_place(place)
    try:
        import osmnx as ox
        return int(ox.nearest_nodes(graph, X=lon, Y=lat))
    except Exception:
        return min(graph.nodes, key=lambda node: squared_distance(graph.nodes[node], lat, lon))


def parse_place(place: str) -> tuple[float, float]:
    """Parse coordinates or geocode a text place."""
    parts = [part.strip() for part in place.split(",")]
    if len(parts) == 2:
        return float(parts[0]), float(parts[1])
    import osmnx as ox
    lat, lon = ox.geocode(place)
    return float(lat), float(lon)


def squared_distance(node_data: dict, lat: float, lon: float) -> float:
    """Return squared coordinate distance."""
    return (float(node_data["y"]) - lat) ** 2 + (float(node_data["x"]) - lon) ** 2


def seconds_by_speed(length_m: float, speed_kmh: float) -> float:
    """Convert edge length and km/h speed to seconds."""
    if speed_kmh <= 0:
        return length_m / 1.34
    return length_m / (speed_kmh * 1000 / 3600)


def normalize_period(period: str) -> str:
    """Normalize Chinese or English period string to standard peak/offpeak/night keys."""
    p = str(period).strip()
    if p in ["尖峰", "上下班尖峰期", "peak"]:
        return "peak"
    elif p in ["深夜", "night"]:
        return "night"
    else:
        return "offpeak"
