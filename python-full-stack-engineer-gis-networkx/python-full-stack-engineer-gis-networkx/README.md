# Empathetic Route Recommendation

將原本的 3S Jupyter Notebook 重構成可部署的 FastAPI + Leaflet 網站。

## 啟動

```bash
pip install -r requirements.txt
uvicorn backend.app:app --reload
```

開啟：

```text
http://127.0.0.1:8000
```

## API

`POST /recommend`

```json
{
  "origin": "25.0478,121.5319",
  "destination": "25.0330,121.5654",
  "gender": "女性",
  "age": 28,
  "height": 160,
  "weight": 50,
  "vehicles": ["walking", "mrt", "bus", "ubike"],
  "complaint": "今天腳不舒服，不想走太久"
}
```

Gemini 只負責自然語言理解，輸出 JSON 權重；路線由 NetworkX 計算。

## 環境變數

可以建立 `.env`：

```text
GEMINI_API_KEY=your_key
CWA_API_KEY=your_key
MOENV_API_KEY=your_key
```

若未設定 API key，系統會使用保守預設值，方便本機先跑通。

## 路網資料

預設不重新下載 OSM 資料。系統會先讀取：

```text
data/graphs/drive.graphml
data/graphs/rail.graphml
data/graphs/walk.graphml
```

若沒有快取，會使用小型 demo graph 讓網站先啟動。若要按 Notebook 的
`ox.graph_from_point((25.040, 121.540), dist=15000, ...)` 建立台北路網：

```text
ALLOW_OSM_DOWNLOAD=true
```
