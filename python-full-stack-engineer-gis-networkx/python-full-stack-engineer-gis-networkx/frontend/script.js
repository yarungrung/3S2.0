const TAIPEI_BOUNDS = [
  [24.95, 121.45],
  [25.22, 121.67],
];

const map = L.map("map", {
  maxBounds: TAIPEI_BOUNDS,
  maxBoundsViscosity: 0.9,
}).setView([25.0478, 121.5319], 12);

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: "&copy; OpenStreetMap",
}).addTo(map);

const routeLayer = L.layerGroup().addTo(map);
const markerLayer = L.layerGroup().addTo(map);
const colors = ["#176b87", "#d62828", "#2f855a"];

addTaipeiMask();
bindEvents();

function bindEvents() {
  document.getElementById("recommend-btn").addEventListener("click", recommend);
  document.getElementById("origin-search").addEventListener("click", () => searchAddress("origin"));
  document.getElementById("destination-search").addEventListener("click", () => searchAddress("destination"));
  document.getElementById("origin-results").addEventListener("change", () => chooseResult("origin"));
  document.getElementById("destination-results").addEventListener("change", () => chooseResult("destination"));
  document.getElementById("private-weight").addEventListener("change", togglePrivateWeight);
  map.on("click", fillPointFromMap);
}

function addTaipeiMask() {
  const outer = [[90, -180], [90, 180], [-90, 180], [-90, -180]];
  const inner = [
    [TAIPEI_BOUNDS[0][0], TAIPEI_BOUNDS[0][1]],
    [TAIPEI_BOUNDS[0][0], TAIPEI_BOUNDS[1][1]],
    [TAIPEI_BOUNDS[1][0], TAIPEI_BOUNDS[1][1]],
    [TAIPEI_BOUNDS[1][0], TAIPEI_BOUNDS[0][1]],
  ];
  L.polygon([outer, inner], {
    color: "#2f4858",
    weight: 1,
    fillColor: "#eff3f5",
    fillOpacity: 0.72,
    interactive: false,
  }).addTo(map);
  L.rectangle(TAIPEI_BOUNDS, {
    color: "#176b87",
    dashArray: "6 6",
    fillOpacity: 0,
    weight: 2,
  }).addTo(map);
}

function fillPointFromMap(event) {
  const lat = event.latlng.lat;
  const lon = event.latlng.lng;
  if (!insideTaipei(lat, lon)) {
    setStatus("請選擇臺北市範圍內的位置。");
    return;
  }
  const target = document.getElementById("origin-address").value.trim() ? "destination" : "origin";
  setPoint(target, lat, lon, "地圖選取位置");
}

async function searchAddress(kind) {
  const address = document.getElementById(`${kind}-address`).value.trim();
  if (!address) {
    setStatus("請先輸入地址或地標。");
    return;
  }
  setStatus("正在搜尋臺北市內地址...");
  const results = await geocode(address);
  renderSearchResults(kind, results);
  setStatus(results.length ? "請從搜尋結果中選擇一個位置。" : "找不到臺北市內的符合地址。");
}

async function geocode(address) {
  const response = await fetch(`/geocode?q=${encodeURIComponent(address)}`);
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

function renderSearchResults(kind, results) {
  const select = document.getElementById(`${kind}-results`);
  select.innerHTML = "";
  results.forEach((item) => {
    const option = document.createElement("option");
    option.value = JSON.stringify(item);
    option.textContent = item.label;
    select.appendChild(option);
  });
  select.hidden = results.length === 0;
  if (results.length) chooseResult(kind);
}

function chooseResult(kind) {
  const select = document.getElementById(`${kind}-results`);
  if (!select.value) return;
  const item = JSON.parse(select.value);
  setPoint(kind, item.lat, item.lon, item.label);
}

function setPoint(kind, lat, lon, label) {
  document.getElementById(kind).value = `${Number(lat).toFixed(6)},${Number(lon).toFixed(6)}`;
  document.getElementById(`${kind}-address`).value = label;
  markerLayer.clearLayers();
  drawSelectedMarkers();
}

function drawSelectedMarkers() {
  ["origin", "destination"].forEach((kind) => {
    const point = parsePoint(document.getElementById(kind).value);
    if (!point) return;
    const color = kind === "origin" ? "green" : "red";
    const label = kind === "origin" ? "起點" : "終點";
    L.marker(point, { title: label }).addTo(markerLayer);
  });
}

async function recommend() {
  const button = document.getElementById("recommend-btn");
  setLoading(button, true);
  try {
    await ensureAddressResolved("origin");
    await ensureAddressResolved("destination");
    const payload = formPayload();
    if (!pointsInsideTaipei(payload)) throw new Error("起點與終點都必須在臺北市範圍內。");
    const response = await fetch("/recommend", requestOptions(payload));
    if (!response.ok) throw new Error(await response.text());
    renderResult(await response.json());
  } catch (error) {
    setStatus(`發生錯誤：${error.message}`);
  } finally {
    setLoading(button, false);
  }
}

async function ensureAddressResolved(kind) {
  if (document.getElementById(kind).value) return;
  const results = await geocode(document.getElementById(`${kind}-address`).value.trim());
  if (!results.length) throw new Error(`${kind === "origin" ? "起點" : "終點"}找不到臺北市內地址。`);
  setPoint(kind, results[0].lat, results[0].lon, results[0].label);
}

function requestOptions(payload) {
  return {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  };
}

function formPayload() {
  return {
    origin: valueOf("origin"),
    destination: valueOf("destination"),
    gender: valueOf("gender"),
    age: Number(valueOf("age")),
    weight: selectedWeight(),
    vehicles: checkedVehicles(),
    complaint: valueOf("complaint"),
  };
}

function selectedWeight() {
  if (document.getElementById("private-weight").checked) return 60;
  const weight = Number(valueOf("weight"));
  return Number.isFinite(weight) && weight > 0 ? weight : 60;
}

function togglePrivateWeight() {
  const input = document.getElementById("weight");
  input.disabled = document.getElementById("private-weight").checked;
  if (input.disabled) input.value = 60;
}

function checkedVehicles() {
  return Array.from(document.querySelectorAll('input[name="vehicles"]:checked')).map((input) => input.value);
}

function pointsInsideTaipei(payload) {
  const origin = parsePoint(payload.origin);
  const destination = parsePoint(payload.destination);
  return origin && destination && insideTaipei(origin[0], origin[1]) && insideTaipei(destination[0], destination[1]);
}

function parsePoint(value) {
  const parts = value.split(",").map(Number);
  if (parts.length !== 2 || parts.some((part) => !Number.isFinite(part))) return null;
  return parts;
}

function insideTaipei(lat, lon) {
  return lat >= TAIPEI_BOUNDS[0][0] && lat <= TAIPEI_BOUNDS[1][0]
    && lon >= TAIPEI_BOUNDS[0][1] && lon <= TAIPEI_BOUNDS[1][1];
}

function valueOf(id) {
  return document.getElementById(id).value.trim();
}

function setStatus(message) {
  document.getElementById("status").textContent = message;
}

function setLoading(button, loading) {
  button.disabled = loading;
  button.textContent = loading ? "推薦中..." : "開始推薦";
  if (loading) setStatus("正在理解需求並計算路線。");
}

function renderResult(data) {
  routeLayer.clearLayers();
  document.getElementById("reasoning").textContent = data.reasoning || "";
  const routes = document.getElementById("routes");
  routes.innerHTML = "";
  const bounds = [];
  data.routes.forEach((route, index) => renderRoute(route, index, routes, bounds));
  if (bounds.length) map.fitBounds(bounds, { padding: [32, 32] });
}

function renderRoute(route, index, container, bounds) {
  const color = colors[index % colors.length];
  const latLngs = route.coordinates.map((point) => [point[0], point[1]]);
  L.polyline(latLngs, { color, weight: 5, opacity: 0.86 }).addTo(routeLayer);
  latLngs.forEach((point) => bounds.push(point));
  container.insertAdjacentHTML("beforeend", routeCard(route, color));
}

function routeCard(route, color) {
  return `
    <article class="route-card" style="border-left: 6px solid ${color}">
      <div class="route-title">
        <span>第 ${route.rank} 名｜${vehicleLabel(route.vehicle)}</span>
        <span>${route.time_minutes} 分鐘</span>
      </div>
      <p class="muted">
        真實時間 ${route.time_minutes} 分鐘，
        票價 ${route.fare} 元，
        距離 ${route.distance_meters} 公尺
      </p>
    </article>
  `;
}

function vehicleLabel(vehicle) {
  const labels = {
    walking: "步行",
    mrt: "捷運",
    bus: "公車",
    train: "台鐵",
    ubike: "YouBike",
    taxi: "計程車",
    car: "汽車",
    scooter: "機車",
  };
  return labels[vehicle] || vehicle;
}
