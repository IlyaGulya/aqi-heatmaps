const MAP_CENTER = [44.7866, 20.4489];
const MAP_ZOOM = 12;
const DATA_URL = "../data/aggregated_aqi.json";

let heatLayer = null;
let allRecords = [];
let mapInstance = null;

const startInput = document.querySelector("#start-input");
const windowInput = document.querySelector("#window-input");
const tableBody = document.querySelector("#station-table");
const summary = document.querySelector("#selection-summary");

function initialiseMap() {
  mapInstance = L.map("map", {
    zoomControl: true,
    attributionControl: false,
  }).setView(MAP_CENTER, MAP_ZOOM);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; <a href='https://www.openstreetmap.org/copyright'>OpenStreetMap</a> contributors",
    maxZoom: 18,
  }).addTo(mapInstance);
}

function fetchData() {
  return fetch(DATA_URL)
    .then((response) => {
      if (!response.ok) {
        throw new Error(`Failed to load data: ${response.statusText}`);
      }
      return response.json();
    })
    .then((data) => {
      allRecords = data.map((record) => ({
        ...record,
        timestamp: new Date(record.timestamp),
      }));
      return allRecords;
    });
}

function toInputValue(date) {
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}

function formatTimestampRange(start, end) {
  return `${start.toUTCString()} to ${end.toUTCString()}`;
}

function filterByWindow(start, windowHours) {
  const end = new Date(start.getTime() + windowHours * 60 * 60 * 1000);
  const grouped = new Map();

  allRecords.forEach((record) => {
    if (record.timestamp >= start && record.timestamp < end) {
      const key = record.station_id;
      if (!grouped.has(key)) {
        grouped.set(key, {
          station_id: record.station_id,
          station_name: record.station_name,
          latitude: record.latitude,
          longitude: record.longitude,
          totalAqi: 0,
          count: 0,
        });
      }
      const current = grouped.get(key);
      current.totalAqi += record.aqi;
      current.count += 1;
    }
  });

  const stations = Array.from(grouped.values()).map((station) => ({
    ...station,
    averageAqi: station.totalAqi / station.count,
  }));

  return { stations, end };
}

function buildHeatPoints(stations) {
  return stations.map((station) => [
    station.latitude,
    station.longitude,
    Math.min(station.averageAqi / 500, 1),
  ]);
}

function colourForAqi(aqi) {
  if (aqi <= 50) return "good";
  if (aqi <= 100) return "moderate";
  if (aqi <= 150) return "unhealthy-sg";
  if (aqi <= 200) return "unhealthy";
  if (aqi <= 300) return "very-unhealthy";
  return "hazardous";
}

function renderTable(stations) {
  tableBody.innerHTML = "";
  if (stations.length === 0) {
    tableBody.innerHTML = '<tr><td colspan="3">No measurements in the selected window.</td></tr>';
    return;
  }

  stations
    .sort((a, b) => b.averageAqi - a.averageAqi)
    .forEach((station) => {
      const tr = document.createElement("tr");
      const stationCell = document.createElement("td");
      stationCell.textContent = station.station_name;
      tr.appendChild(stationCell);

      const aqiCell = document.createElement("td");
      aqiCell.textContent = station.averageAqi.toFixed(1);
      aqiCell.classList.add(colourForAqi(station.averageAqi));
      tr.appendChild(aqiCell);

      const countCell = document.createElement("td");
      countCell.textContent = station.count;
      tr.appendChild(countCell);

      tableBody.appendChild(tr);
    });
}

function renderHeatmap(stations) {
  const heatPoints = buildHeatPoints(stations);
  if (heatLayer) {
    heatLayer.setLatLngs(heatPoints);
  } else {
    heatLayer = L.heatLayer(heatPoints, {
      radius: 40,
      blur: 25,
      maxZoom: 17,
      gradient: {
        0.1: "#4ade80",
        0.3: "#facc15",
        0.5: "#f97316",
        0.7: "#ef4444",
        0.85: "#a855f7",
        1.0: "#7f1d1d",
      },
    }).addTo(mapInstance);
  }
}

function updateView() {
  if (!allRecords.length) {
    return;
  }

  const windowHours = parseInt(windowInput.value, 10);
  const start = new Date(startInput.value);
  if (Number.isNaN(windowHours) || windowHours <= 0 || Number.isNaN(start.getTime())) {
    return;
  }

  const { stations, end } = filterByWindow(start, windowHours);
  renderHeatmap(stations);
  renderTable(stations);
  const measurementCount = stations.reduce((acc, station) => acc + station.count, 0);
  summary.textContent = `Averaging ${measurementCount} measurements across ${stations.length} stations between ${formatTimestampRange(
    start,
    end
  )}`;
}

function initialiseControls() {
  const timestamps = allRecords.map((record) => record.timestamp.getTime());
  const minTimestamp = new Date(Math.min(...timestamps));
  const maxTimestamp = new Date(Math.max(...timestamps));
  startInput.min = toInputValue(minTimestamp);
  startInput.max = toInputValue(maxTimestamp);
  startInput.value = toInputValue(minTimestamp);
  updateView();
}

function wireEvents() {
  const form = document.querySelector("#controls-form");
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    updateView();
  });

  startInput.addEventListener("change", updateView);
  windowInput.addEventListener("input", updateView);
}

function bootstrap() {
  initialiseMap();
  fetchData()
    .then(() => {
      initialiseControls();
      wireEvents();
    })
    .catch((error) => {
      summary.textContent = error.message;
    });
}

document.addEventListener("DOMContentLoaded", bootstrap);
