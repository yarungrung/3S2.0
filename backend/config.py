# backend/config.py
import os
from pathlib import Path
from functools import lru_cache
import streamlit as st

# 這是 Streamlit 官方建議的讀取方式
api_key = st.secrets.get("CWA_API_KEY")

# ==========================================
# 1. API 金鑰 (從環境變數讀取)
# ==========================================
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY")
WEATHER_API_KEY = st.secrets.get("WEATHER_API_KEY") or os.environ.get("CWA_API_KEY")
MOENV_API_KEY = st.secrets.get("MOENV_API_KEY")

# 交通部 TDX API 金鑰 (備用)
TDX_APP_ID = st.secrets.get("TDX_APP_ID")
TDX_APP_KEY = st.secrets.get("TDX_APP_KEY")

# 安全防護警告：核心大腦金鑰若遺失，以 warning 提醒，不中斷啟動以利離線測試與部屬
if not GEMINI_API_KEY:
    print("[Warning] 未在環境變數中偵測到 GEMINI_API_KEY，同理心推薦語與偏好權重將採用靜態預設值進行展示。")

# ==========================================
# 2. 模型與參數設定
# ==========================================
GEMINI_MODEL_NAME = st.secrets.get("GEMINI_MODEL", "gemini-3.5-flash")

# ==========================================
# 3. 專案路徑設定 (動態定位，避免跨平台路徑錯誤)
# ==========================================
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "backend" / "data"
GRAPH_CACHE_DIR = DATA_DIR / "graphs"

# 確保資料夾存在
DATA_DIR.mkdir(parents=True, exist_ok=True)
GRAPH_CACHE_DIR.mkdir(parents=True, exist_ok=True)

class Settings:
    """FastAPI settings adapter for submodules compatibilities."""
    app_name: str = "Empathetic Route Recommendation"
    frontend_dir: Path = BASE_DIR / "frontend"
    data_dir: Path = DATA_DIR
    graph_cache_dir: Path = GRAPH_CACHE_DIR
    gemini_api_key: str | None = GEMINI_API_KEY
    cwa_api_key: str | None = WEATHER_API_KEY
    moenv_api_key: str | None = MOENV_API_KEY
    gemini_model: str = GEMINI_MODEL_NAME
    taipei_center: tuple[float, float] = (25.040, 121.540)
    search_dist_m: int = 9000
    default_travel_period: str = os.environ.get("TRAVEL_PERIOD", "離峰期")
    allow_osm_download: bool = os.environ.get("ALLOW_OSM_DOWNLOAD", "true").lower() == "true"

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
