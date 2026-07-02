"""Graph construction and edge attribute injection from the notebook."""

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any

import networkx as nx

from backend.config import get_settings
from backend.routing.fare import bus_fare, mrt_fare, taxi_fare, train_fare, ubike_fare
from backend.routing.waiting_time import match_mrt_wait_seconds, mrt_wait_minutes
from backend.routing.walking_speed import calculate_walk_speed, fare_identity


@dataclass
class RoutingGraphs:
    """Container for Taipei multimodal graphs."""

    drive: nx.MultiDiGraph
    rail: nx.MultiDiGraph
    walk: nx.MultiDiGraph


def build_graphs() -> RoutingGraphs:
    """Load cached graphs or build Taipei graphs with the notebook method."""
    settings = get_settings()
    cached = load_cached_graphs(settings.graph_cache_dir)
    if cached:
        return cached
    if not settings.allow_osm_download:
        return build_demo_graphs()
    try:
        graphs = download_osmnx_graphs(settings.taipei_center, settings.search_dist_m)
        save_cached_graphs(graphs, settings.graph_cache_dir)
        return graphs
    except Exception:
        return build_demo_graphs()


def load_cached_graphs(cache_dir: Path) -> RoutingGraphs | None:
    """Load GraphML cache if present."""
    paths = {name: cache_dir / f"{name}.graphml" for name in ("drive", "rail", "walk")}
    if not all(path.exists() for path in paths.values()):
        return None
    try:
        import osmnx as ox

        return RoutingGraphs(
            drive=ox.load_graphml(paths["drive"]),
            rail=ox.load_graphml(paths["rail"]),
            walk=ox.load_graphml(paths["walk"]),
        )
    except Exception:
        return None


def save_cached_graphs(graphs: RoutingGraphs, cache_dir: Path) -> None:
    """Save graphs to GraphML cache."""
    try:
        import osmnx as ox

        ox.save_graphml(graphs.drive, cache_dir / "drive.graphml")
        ox.save_graphml(graphs.rail, cache_dir / "rail.graphml")
        ox.save_graphml(graphs.walk, cache_dir / "walk.graphml")
    except Exception:
        return


def download_osmnx_graphs(center: tuple[float, float], dist: int) -> RoutingGraphs:
    """Build Taipei graphs using the notebook's OSMnx graph_from_point calls."""
    import networkx as nx_local
    import osmnx as ox

    drive = ox.graph_from_point(center, dist=dist, network_type="drive")
    rail = ox.graph_from_point(center, dist=dist, custom_filter='["railway"~"subway|rail|light_rail"]')
    walk = ox.graph_from_point(center, dist=dist, network_type="walk")
    drive = keep_largest_strong_component(drive, nx_local)
    rail = keep_largest_strong_component(rail, nx_local)
    walk = keep_largest_strong_component(walk, nx_local)
    return RoutingGraphs(drive=drive, rail=rail, walk=walk)


def keep_largest_strong_component(graph: nx.MultiDiGraph, nx_module: Any = nx) -> nx.MultiDiGraph:
    """Keep the largest strongly connected component, matching the notebook."""
    nodes = max(nx_module.strongly_connected_components(graph), key=len)
    return graph.subgraph(nodes).copy()


def prepare_graphs(
    graphs: RoutingGraphs,
    age: int,
    gender: str,
    weight: float,
    walk_multiplier: float,
    travel_period: str,
    wind_speed: float = 2.5,
    wind_direction: float = 90.0,
) -> RoutingGraphs:
    """Inject time and fare attributes without changing notebook formulas."""
    identity = fare_identity(age)
    walk_speed = calculate_walk_speed(age, gender) * walk_multiplier
    wait_table = mrt_wait_minutes(travel_period)
    inject_drive_edges(graphs.drive, identity)
    inject_rail_edges(graphs.rail, identity, wait_table)
    inject_walk_edges(graphs.walk, identity, walk_speed, weight, wind_speed, wind_direction)
    inject_safety_defaults(graphs)
    return graphs


def inject_drive_edges(graph: nx.MultiDiGraph, identity: str) -> None:
    """Inject car, motorcycle, taxi, and bus time/fare attributes."""
    speeds = {"car": 19.87, "motorcycle": 23.0, "taxi": 19.87, "bus": 15.86}
    for _, _, _, data in graph.edges(data=True, keys=True):
        length_m = float(data.get("length", 1.0))
        length_km = length_m / 1000.0
        data["pure_time_car"] = seconds_by_speed(length_m, speeds["car"])
        data["pure_fare_car"] = length_km * 3.5
        data["pure_time_motorcycle"] = seconds_by_speed(length_m, speeds["motorcycle"])
        data["pure_fare_motorcycle"] = length_km * 0.8
        data["pure_time_taxi"] = seconds_by_speed(length_m, speeds["taxi"])
        data["pure_fare_taxi"] = taxi_fare(length_km)
        data["pure_time_bus"] = seconds_by_speed(length_m, speeds["bus"])
        data["pure_fare_bus"] = bus_fare(identity)


def inject_rail_edges(graph: nx.MultiDiGraph, identity: str, wait_table: dict) -> None:
    """Inject MRT and train time/fare attributes."""
    for _, _, _, data in graph.edges(data=True, keys=True):
        length_m = float(data.get("length", 1.0))
        length_km = length_m / 1000.0
        run_time_mrt = seconds_by_speed(length_m, 31.43)
        data["pure_time_mrt"] = run_time_mrt + match_mrt_wait_seconds(data, wait_table)
        data["pure_fare_mrt"] = mrt_fare(length_km, identity)
        data["pure_time_train"] = seconds_by_speed(length_m, 40.0)
        data["pure_fare_train"] = train_fare(length_km, identity)


def inject_walk_edges(
    graph: nx.MultiDiGraph,
    identity: str,
    walk_speed: float,
    weight: float,
    wind_speed: float,
    wind_direction: float,
) -> None:
    """Inject walk and YouBike attributes, including wind resistance."""
    constants = bike_constants(weight)
    wind_rad = math.radians(wind_direction)
    for u, v, _, data in graph.edges(data=True, keys=True):
        length_m = float(data.get("length", 1.0))
        data["pure_time_walk"] = seconds_by_speed(length_m, walk_speed)
        bike_ms = adjusted_bike_speed(graph, u, v, wind_speed, wind_rad, constants)
        data["pure_time_youbike"] = length_m / bike_ms
        data["pure_fare_walk"] = 0.0
        data["pure_fare_youbike"] = ubike_fare(data["pure_time_youbike"] / 60.0, identity)


def bike_constants(weight: float) -> dict[str, float]:
    """Return constants from the notebook's YouBike wind model."""
    bike_weight = 22.0
    mass = bike_weight + weight
    return {
        "power": 27.36,
        "rolling_const": 0.008 * mass * 9.81,
        "air_const": 0.5 * 1.2 * 0.6,
    }


def adjusted_bike_speed(graph: nx.MultiDiGraph, u: int, v: int, wind_speed: float, wind_rad: float, c: dict) -> float:
    """Run the notebook's five-step Newton iteration for YouBike speed."""
    u_data, v_data = graph.nodes[u], graph.nodes[v]
    street_rad = math.atan2(v_data["x"] - u_data["x"], v_data["y"] - u_data["y"])
    effective_wind = wind_speed * math.cos(street_rad - wind_rad)
    guess = 2.78
    for _ in range(5):
        relative_v = guess - effective_wind
        f_v = c["air_const"] * guess * (relative_v**2) + c["rolling_const"] * guess - c["power"]
        df_v = c["air_const"] * (relative_v**2) + 2 * c["air_const"] * guess * relative_v + c["rolling_const"]
        if abs(df_v) < 1e-5:
            break
        guess = guess - f_v / df_v
        if guess <= 0:
            guess = 0.5
            break
    return max(1.5, min(6.0, guess))


def seconds_by_speed(length_m: float, speed_kmh: float) -> float:
    """Convert edge length and km/h speed to seconds."""
    return length_m / (speed_kmh * 1000 / 3600)


def inject_safety_defaults(graphs: RoutingGraphs) -> None:
    """Preserve safety-cost attributes, using neutral defaults if data is absent."""
    for _, _, _, data in graphs.walk.edges(data=True, keys=True):
        data.setdefault("safety_cost_walk", 0.0)
        data.setdefault("safety_cost_youbike", 0.0)
    for _, _, _, data in graphs.drive.edges(data=True, keys=True):
        data.setdefault("safety_cost_bus", 0.0)
        data.setdefault("safety_cost_car", 0.0)
        data.setdefault("safety_cost_motorcycle", 0.0)
    for _, _, _, data in graphs.rail.edges(data=True, keys=True):
        data.setdefault("safety_cost_mrt", 0.0)
        data.setdefault("safety_cost_train", 0.0)


def build_demo_graphs() -> RoutingGraphs:
    """Build a tiny Taipei-shaped fallback graph for local smoke tests."""
    drive = build_demo_graph("drive", 8)
    rail = build_demo_graph("rail", 5)
    walk = build_demo_graph("walk", 10)
    return RoutingGraphs(drive=drive, rail=rail, walk=walk)


def build_demo_graph(name: str, count: int) -> nx.MultiDiGraph:
    """Create a deterministic fallback MultiDiGraph."""
    graph = nx.MultiDiGraph(name=name, crs="EPSG:4326")
    for index in range(count):
        graph.add_node(index, y=25.02 + index * 0.006, x=121.50 + index * 0.008)
    for index in range(count - 1):
        length = 900 + index * 120
        graph.add_edge(index, index + 1, length=length, name=f"{name}-{index}")
        graph.add_edge(index + 1, index, length=length, name=f"{name}-{index}-r")
    add_demo_shortcuts(graph, count)
    return graph


def add_demo_shortcuts(graph: nx.MultiDiGraph, count: int) -> None:
    """Add alternative paths so top-three routing has candidates."""
    for index in range(count - 2):
        graph.add_edge(index, index + 2, length=1900 + index * 140, name=f"shortcut-{index}")
        graph.add_edge(index + 2, index, length=1900 + index * 140, name=f"shortcut-{index}-r")
