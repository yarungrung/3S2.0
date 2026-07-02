"""NetworkX routing engine."""

from dataclasses import dataclass
from typing import Any

import networkx as nx

from backend.config import get_settings
from backend.routing.graph import RoutingGraphs, build_graphs, prepare_graphs
from backend.weather.weather_api import WeatherSnapshot


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
    vehicles: list[str]
    ai_result: dict[str, Any]
    weather: WeatherSnapshot


_GRAPHS: RoutingGraphs | None = None


def recommend_routes(data: RouteRequestData) -> list[dict[str, Any]]:
    """Return the top three NetworkX routes after applying AI weights."""
    graphs = get_prepared_graphs(data)
    candidates = []
    for vehicle in allowed_vehicles(data):
        route = route_for_vehicle(graphs, vehicle, data.origin, data.destination, data.ai_result)
        candidates.extend(route)
    candidates.sort(key=lambda item: item["adjusted_time_seconds"])
    return candidates[:3]


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


def allowed_vehicles(data: RouteRequestData) -> list[str]:
    """Apply user-selected vehicles and Gemini banned vehicle filtering."""
    requested = data.vehicles or list(VEHICLE_MODES.keys())
    banned = {normalize_vehicle(v) for v in data.ai_result.get("banned_vehicles", [])}
    allowed = []
    for vehicle in requested:
        normalized = normalize_vehicle(vehicle)
        if normalized in VEHICLE_MODES and normalized not in banned:
            allowed.append(normalized)
    return sorted(set(allowed))


def route_for_vehicle(graphs: RoutingGraphs, vehicle: str, origin: str, destination: str, ai: dict) -> list[dict]:
    """Calculate up to three routes for one vehicle."""
    graph_name, mode = VEHICLE_MODES[vehicle]
    graph = getattr(graphs, graph_name)
    source = nearest_node(graph, origin)
    target = nearest_node(graph, destination)
    weight = mode_weight(vehicle, ai)
    weighted = weighted_digraph(graph, mode, weight)
    paths = shortest_paths(weighted, source, target, 3)
    return [summarize_path(graph, path, vehicle, mode, weight, index + 1) for index, path in enumerate(paths)]


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
    return float(weights.get(aliases.get(vehicle, vehicle), 1.0))


def weighted_digraph(graph: nx.MultiDiGraph, mode: str, weight: float) -> nx.DiGraph:
    """Create a DiGraph with adjusted_time for NetworkX shortest paths."""
    result = nx.DiGraph()
    time_key = f"pure_time_{mode}"
    safety_key = f"safety_cost_{mode}"
    for u, v, edge_data in graph.edges(data=True):
        time_value = float(edge_data.get(time_key, edge_data.get("length", 1.0)))
        adjusted = time_value * weight * (1.0 + float(edge_data.get(safety_key, 0.0)))
        keep_best_edge(result, u, v, adjusted)
    return result


def keep_best_edge(graph: nx.DiGraph, u: int, v: int, adjusted: float) -> None:
    """Keep the lowest adjusted_time edge between two nodes."""
    if graph.has_edge(u, v) and graph[u][v]["adjusted_time"] <= adjusted:
        return
    graph.add_edge(u, v, adjusted_time=adjusted)


def shortest_paths(graph: nx.DiGraph, source: int, target: int, count: int) -> list[list[int]]:
    """Return up to count shortest simple paths."""
    try:
        generator = nx.shortest_simple_paths(graph, source, target, weight="adjusted_time")
        return [path for _, path in zip(range(count), generator)]
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return []


def summarize_path(graph: nx.MultiDiGraph, path: list[int], vehicle: str, mode: str, weight: float, rank: int) -> dict:
    """Summarize time, fare, distance, and geometry for one path."""
    totals = {"time": 0.0, "fare": 0.0, "distance": 0.0, "adjusted": 0.0}
    coordinates = [[graph.nodes[path[0]]["y"], graph.nodes[path[0]]["x"]]]
    for u, v in zip(path[:-1], path[1:]):
        edge = best_multiedge(graph, u, v, mode)
        pure_time = float(edge.get(f"pure_time_{mode}", 0.0))
        totals["fare"] += float(edge.get(f"pure_fare_{mode}", 0.0))
        totals["time"] += pure_time
        totals["distance"] += float(edge.get("length", 0.0))
        totals["adjusted"] += pure_time * weight * (1.0 + float(edge.get(f"safety_cost_{mode}", 0.0)))
        coordinates.append([graph.nodes[v]["y"], graph.nodes[v]["x"]])
    return route_payload(rank, vehicle, totals, coordinates)


def best_multiedge(graph: nx.MultiDiGraph, u: int, v: int, mode: str) -> dict:
    """Return the fastest edge data between two nodes for the chosen mode."""
    edges = graph.get_edge_data(u, v, default={})
    time_key = f"pure_time_{mode}"
    return min(edges.values(), key=lambda data: float(data.get(time_key, data.get("length", 1.0))))


def route_payload(rank: int, vehicle: str, totals: dict[str, float], coordinates: list[list[float]]) -> dict:
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


def nearest_node(graph: nx.MultiDiGraph, place: str) -> int:
    """Find nearest graph node from 'lat,lon' or a geocoded place string."""
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
