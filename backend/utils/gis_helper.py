import os
from pathlib import Path
import geopandas as gpd
from shapely.geometry import Point
from typing import Dict, List, Optional, Any
from backend.models.schemas import StationItem

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "backend" / "data"

# In-memory caches
_STATIONS_CACHE: Dict[str, List[StationItem]] = {}
_TAIPEI_BOUNDARY_CACHE: Optional[Dict[str, Any]] = None
_TOWN_GDF_CACHE: Optional[gpd.GeoDataFrame] = None

def load_shapefile_stations(folder_name: str, file_pattern: str, mode_label: str) -> List[StationItem]:
    """
    Read a shapefile using geopandas, extract points, and return list of StationItem.
    """
    folder_path = DATA_DIR / folder_name
    shp_files = list(folder_path.glob(file_pattern))
    if not shp_files:
        print(f"[Warning] No shapefiles matching {file_pattern} found in {folder_path}")
        return []
    
    shp_file_path = shp_files[0]
    try:
        gdf = gpd.read_file(str(shp_file_path))
        if gdf.crs is not None and gdf.crs.to_epsg() != 4326:
            gdf = gdf.to_crs(epsg=4326)
            
        stations = []
        for index, row in gdf.iterrows():
            geom = row.geometry
            if geom is not None and hasattr(geom, 'x') and hasattr(geom, 'y'):
                name = f"{mode_label}站 {index + 1}"
                stations.append(StationItem(
                    name=name,
                    lat=float(geom.y),
                    lon=float(geom.x)
                ))
        return stations
    except Exception as e:
        print(f"[Error] Error loading shapefile {shp_file_path}: {e}")
        return []

def get_all_stations() -> Dict[str, List[StationItem]]:
    """
    Fetch all stations from shapefiles, caching results in-memory.
    """
    global _STATIONS_CACHE
    if not _STATIONS_CACHE:
        print("=== 正在讀取 MRT, TRAIN, BUS 站點 Shapefiles ===")
        mrt_stations = load_shapefile_stations("MRT", "*.shp", "捷運")
        train_stations = load_shapefile_stations("TRAIN", "*.shp", "火車站")
        bus_stations = load_shapefile_stations("BUS", "*.shp", "公車")
        
        _STATIONS_CACHE = {
            "mrt": mrt_stations,
            "train": train_stations,
            "bus": bus_stations
        }
        print(f"[Success] 成功載入站點統計 -> 捷運: {len(mrt_stations)}個, 火車: {len(train_stations)}個, 公車: {len(bus_stations)}個")
        
    return _STATIONS_CACHE

def get_taipei_boundary_coords() -> Dict[str, Any]:
    """
    Load the county shapefile, extract Taipei City boundary, 
    simplify it for Leaflet rendering, and return its coords.
    """
    global _TAIPEI_BOUNDARY_CACHE
    if _TAIPEI_BOUNDARY_CACHE is not None:
        return _TAIPEI_BOUNDARY_CACHE
        
    folder_path = DATA_DIR / "直轄市、縣(市)界線1140318"
    shp_files = list(folder_path.glob("*.shp"))
    if not shp_files:
        print("[Warning] County shapefile not found under 直轄市、縣(市)界線1140318. Using default bounds.")
        return {
            "exterior": [[24.95, 121.45], [25.22, 121.45], [25.22, 121.67], [24.95, 121.67]],
            "interiors": []
        }
        
    try:
        gdf = gpd.read_file(str(shp_files[0])).to_crs(epsg=4326)
        taipei_geom = gdf[gdf['COUNTYNAME'] == '臺北市'].geometry.iloc[0]
        
        # Simplify geometry to ~480 vertices to ensure map runs smoothly in browser
        simplified = taipei_geom.simplify(0.0002, preserve_topology=True)
        
        exterior = [[coord[1], coord[0]] for coord in simplified.exterior.coords]
        interiors = [[[coord[1], coord[0]] for coord in interior.coords] for interior in simplified.interiors]
        
        _TAIPEI_BOUNDARY_CACHE = {
            "exterior": exterior,
            "interiors": interiors
        }
        return _TAIPEI_BOUNDARY_CACHE
    except Exception as e:
        print(f"[Error] Failed to load or simplify Taipei boundary shapefile: {e}")
        return {
            "exterior": [[24.95, 121.45], [25.22, 121.45], [25.22, 121.67], [24.95, 121.67]],
            "interiors": []
        }

def get_district_by_coords(lat: float, lon: float) -> str:
    """
    Perform a spatial check using TOWN_MOI_1140318.shp to check which
    Taipei City district contains the given coordinate.
    """
    global _TOWN_GDF_CACHE
    if _TOWN_GDF_CACHE is None:
        folder_path = DATA_DIR / "鄉鎮市"
        shp_files = list(folder_path.glob("*.shp"))
        if not shp_files:
            print("[Warning] Town shapefiles not found under 鄉鎮市.")
            return "未知區"
        try:
            # Load and cache town boundaries, pre-filtering for Taipei City
            gdf = gpd.read_file(str(shp_files[0])).to_crs(epsg=4326)
            _TOWN_GDF_CACHE = gdf[gdf['COUNTYNAME'] == '臺北市']
        except Exception as e:
            print(f"[Error] Failed to load town boundary shapefile: {e}")
            return "未知區"
            
    p = Point(lon, lat)
    for _, row in _TOWN_GDF_CACHE.iterrows():
        if row.geometry is not None and row.geometry.contains(p):
            return str(row['TOWNNAME'])
            
    return "境外"

def find_nearest_station(lat: float, lon: float, mode: str) -> Optional[Dict[str, Any]]:
    """
    Find the closest shapefile station (MRT, Train, or Bus) to the given coordinate.
    """
    stations = get_all_stations()
    stations_list = []
    if mode == "mrt":
        stations_list = stations.get("mrt", [])
    elif mode == "train":
        stations_list = stations.get("train", [])
    elif mode == "bus":
        stations_list = stations.get("bus", [])
        
    if not stations_list:
        return None
        
    best_st = min(stations_list, key=lambda st: (st.lat - lat)**2 + (st.lon - lon)**2)
    return {
        "name": best_st.name,
        "lat": best_st.lat,
        "lon": best_st.lon
    }
