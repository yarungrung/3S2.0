# 🗺️ 臺北市智慧通勤導遊 3.0 (Empathetic Route Advisor 3.0)

這是一個具備「同理心」的台北市多模式交通路線偏好推薦系統。結合了 FastAPI 後端與 Leaflet 前端，能將使用者的生理基礎、自由抱怨對話、即時天氣與空氣品質(AQI)轉化為 NetworkX 路網權重，精準篩選出前 3 名最合適的通勤路線，並以輕量淺藍玻璃感 (Light Blue Glassmorphism) 的 premium 視覺效果呈現在地圖上。

## 🌟 系統特色
1. **同理心權重轉換大腦 (Gemini 3.5 Flash)**：將人類模糊的心情與抱怨轉譯為圖論演算法看得懂的交通工具成本乘數 (Edge Weight Multipliers)。
2. **多模式交通路網 (Multi-modal Network)**：包含開車、機車、計程車、公車、YouBike、捷運、步行、火車 8 種交通模式。
3. **即時天氣與空氣品質 (API 感知)**：串接中央氣象署觀測與預報資料（氣溫、降雨量、降雨機率），以及環境部即時 AQI。
4. **GeoData Shapefile 站點點位視覺化**：使用 Geopandas 動態讀取 `MRT`、`TRAIN`、`BUS` 資料夾中的 Shapefile 檔，並利用 Leaflet 渲染圓形標記（具備圖層切換控制，提升渲染效能）。
5. **雙指標公式計算**：路線規劃後，還原計算出真實物理的「預估時間」與「官方車資」。

---

## 🛠️ 開發自訂與修改指引 (Customization Guide)

如您在競賽或後續開發中需要調整**安全係數**或**公車與計程車車資**，請參閱以下標註檔案與位置：

### 1. 🚖 計程車費率公式 (Taxi Fare)
* **修改檔案**：[backend/routing/fare.py](file:///d:/NCUE/3S/backend/routing/fare.py)
* **修改位置**：`taxi_fare(length_km, is_night_surge)` 函式。
* **說明**：內含起跳價、每200公尺加收費用以及夜間加成的費率邏輯，已在代碼中以 `【使用者自訂區域：計程車費率公式】` 標記。

### 2. 🚌 公車費率公式 (Bus Fare)
* **修改檔案**：[backend/routing/fare.py](file:///d:/NCUE/3S/backend/routing/fare.py)
* **修改位置**：`bus_fare(identity)` 函式。
* **說明**：內含成人票、學生悠遊卡、敬老與兒童卡分段收費邏輯，已在代碼中以 `【使用者自訂區域：公車費率公式】` 標記。

### 3. 🛡️ 各運具環境安全敏感度係數 (Safety Coefficients)
* **修改檔案**：[backend/routing/routing.py](file:///d:/NCUE/3S/backend/routing/routing.py)
* **修改位置**：`SAFETY_COEFFICIENTS` 字典。
* **說明**：定義了各運具（步行、YouBike、汽車、機車、公車等）的安全敏感係數。係數越大，規劃路線時越會刻意繞開不安全路段（例如車禍黑點），已在代碼中以 `【使用者自訂區域：各運具之環境安全係數】` 標記。

### 4. 🛡️ 道路安全/風險值初始化與資料注入
* **修改檔案**：[backend/routing/graph.py](file:///d:/NCUE/3S/backend/routing/graph.py)
* **修改位置**：`inject_safety_defaults(graphs)` 函式。
* **說明**：用於在台北市路網中注入不安全路段屬性（如車禍點位 STRtree 查詢結果）。已在代碼中以 `【使用者自訂區域：安全係數 (環境風險值) 注入與初始化】` 標記。

---

## 🚀 快速啟動 (Quick Start)

### 1. 環境準備
請確保您的機器上已安裝 Anaconda 或 Miniconda，並啟用含有必要 GIS 依賴的環境。本專案將預設以 `final` 環境執行：
```bash
conda activate final
```
若缺少 `fastapi` 或 `uvicorn`，可透過 requirements 一鍵安裝：
```bash
pip install -r requirements.txt
```

### 2. 環境變數設定
專案需要設定 API 金鑰來發揮完整功能：
* **Windows PowerShell**:
  ```powershell
  $env:GEMINI_API_KEY="您的_Gemini_API_Key"
  $env:WEATHER_API_KEY="您的_氣象署_API_Key" # 可選
  $env:MOENV_API_KEY="您的_環境部_API_Key"  # 可選
  ```

* **Linux / macOS**:
  ```bash
  export GEMINI_API_KEY="您的_Gemini_API_Key"
  export WEATHER_API_KEY="您的_氣象署_API_Key"
  export MOENV_API_KEY="您的_環境部_API_Key"
  ```

### 3. 啟動伺服器
進入專案根目錄，執行以下命令啟動 FastAPI 服務：
```bash
python -m uvicorn backend.app:app --host 0.0.0.0 --port 5000 --reload
```

### 4. 瀏覽網頁
打開瀏覽器訪問 [http://localhost:5000](http://localhost:5000)，即可開始使用智慧多模式同理心推薦系統。
