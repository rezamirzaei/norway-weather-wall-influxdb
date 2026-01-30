(() => {
  const mapEl = document.getElementById("weather-map");
  if (!mapEl || typeof L === "undefined") return;

  const pollUrl = mapEl.dataset.pollUrl || "/ui/weather/latest.json";
  const pollIntervalMs = Number(mapEl.dataset.pollIntervalMs || 1000);
  const statusEl = document.getElementById("weather-live-status");
  const updatedAtEl = document.getElementById("weather-updated-at");
  const tableBodyEl = document.getElementById("weather-table-body");

  const map = L.map("weather-map", {
    zoomControl: true,
    scrollWheelZoom: false,
  }).setView([64.5, 11.0], 4);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 18,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  }).addTo(map);

  const tempColor = (t) => {
    if (t === null || t === undefined || Number.isNaN(Number(t))) return "#9aa6c0";
    const v = Number(t);
    if (v <= -10) return "#1c7ed6"; // deep cold
    if (v <= -5) return "#339af0";
    if (v <= 0) return "#4dabf7";
    if (v <= 5) return "#51cf66";
    if (v <= 10) return "#fcc419";
    return "#ff6b6b"; // warm/hot
  };

  const fmt = (v, suffix = "") =>
    v === null || v === undefined || v === "" ? "—" : `${v}${suffix}`;

  const esc = (v) =>
    String(v ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");

  const markersByCity = new Map();
  let didFitBounds = false;

  const upsertMarker = (r) => {
    const lat = Number(r.lat);
    const lon = Number(r.lon);
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) return;

    const t = r.air_temperature;
    const color = tempColor(t);

    const popup = `
      <strong>${esc(r.city)}</strong><br/>
      Temp: ${esc(fmt(t, " °C"))}<br/>
      Humidity: ${esc(fmt(r.relative_humidity, " %"))}<br/>
      Wind: ${esc(fmt(r.wind_speed, " m/s"))}<br/>
      Pressure: ${esc(fmt(r.air_pressure_at_sea_level, " hPa"))}<br/>
      Precip 1h: ${esc(fmt(r.precipitation_amount_1h, " mm"))}<br/>
      Symbol: ${esc(fmt(r.symbol_code))}<br/>
      <span style="color:#6b7280">UTC: ${esc(fmt(r.timestamp))}</span>
    `;

    const key = String(r.city ?? "");
    const existing = markersByCity.get(key);
    if (existing) {
      existing.setLatLng([lat, lon]);
      existing.setStyle({ color, fillColor: color });
      if (existing.getPopup()) {
        existing.setPopupContent(popup);
      } else {
        existing.bindPopup(popup, { maxWidth: 260 });
      }
      return;
    }

    const marker = L.circleMarker([lat, lon], {
      radius: 12,
      color,
      weight: 2,
      fillColor: color,
      fillOpacity: 0.65,
    }).addTo(map);
    marker.bindPopup(popup, { maxWidth: 260 });
    markersByCity.set(key, marker);
  };

  const renderTable = (rows) => {
    if (!tableBodyEl) return;
    const sorted = [...rows].sort((a, b) => String(a.city).localeCompare(String(b.city)));
    if (!sorted.length) {
      tableBodyEl.innerHTML =
        '<tr><td colspan="8" class="muted">Waiting for first data point…</td></tr>';
      return;
    }
    tableBodyEl.innerHTML = sorted
      .map(
        (r) => `
      <tr>
        <td>${esc(r.city)}</td>
        <td>${esc(fmt(r.air_temperature))}</td>
        <td>${esc(fmt(r.relative_humidity))}</td>
        <td>${esc(fmt(r.wind_speed))}</td>
        <td>${esc(fmt(r.air_pressure_at_sea_level))}</td>
        <td>${esc(fmt(r.precipitation_amount_1h))}</td>
        <td>${esc(fmt(r.symbol_code))}</td>
        <td>${esc(fmt(r.timestamp))}</td>
      </tr>`
      )
      .join("");
  };

  const renderAll = (rows) => {
    const arr = Array.isArray(rows) ? rows : [];
    const points = [];
    arr.forEach((r) => {
      upsertMarker(r);
      const lat = Number(r.lat);
      const lon = Number(r.lon);
      if (Number.isFinite(lat) && Number.isFinite(lon)) {
        points.push([lat, lon]);
      }
    });
    if (!didFitBounds && points.length) {
      map.fitBounds(points, { padding: [24, 24] });
      didFitBounds = true;
    }
    renderTable(arr);
    if (updatedAtEl) {
      updatedAtEl.textContent = new Date().toISOString().replace(".000Z", "Z");
    }
  };

  const legend = L.control({ position: "bottomright" });
  legend.onAdd = () => {
    const div = L.DomUtil.create("div", "card");
    div.style.padding = "10px 12px";
    div.style.background = "rgba(18, 26, 51, 0.9)";
    div.style.border = "1px solid rgba(34, 48, 90, 0.9)";
    div.style.borderRadius = "12px";
    div.style.color = "#eef2ff";
    div.style.fontSize = "12px";
    div.innerHTML = `
      <div style="font-weight:700;margin-bottom:6px;">Temperature</div>
      <div style="display:grid;gap:4px;">
        ${legendRow("#1c7ed6", "≤ -10°C")}
        ${legendRow("#339af0", "-10..-5°C")}
        ${legendRow("#4dabf7", "-5..0°C")}
        ${legendRow("#51cf66", "0..5°C")}
        ${legendRow("#fcc419", "5..10°C")}
        ${legendRow("#ff6b6b", "> 10°C")}
      </div>
    `;
    return div;
  };
  legend.addTo(map);

  function legendRow(color, label) {
    return `
      <div style="display:flex;align-items:center;gap:8px;">
        <span style="width:10px;height:10px;border-radius:999px;background:${color};display:inline-block;"></span>
        <span>${label}</span>
      </div>
    `;
  }

  const setStatus = (text, ok) => {
    if (!statusEl) return;
    statusEl.textContent = text;
    statusEl.style.color = ok ? "#9aa6c0" : "#ff6b6b";
  };

  let inFlight = false;
  const pollOnce = async () => {
    if (inFlight) return;
    inFlight = true;
    try {
      const resp = await fetch(pollUrl, {
        headers: { Accept: "application/json" },
        cache: "no-store",
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      renderAll(data);
      setStatus("Live: connected", true);
    } catch (_err) {
      setStatus("Live: disconnected", false);
    } finally {
      inFlight = false;
    }
  };

  const initialRows = Array.isArray(window.WEATHER_ROWS) ? window.WEATHER_ROWS : [];
  renderAll(initialRows);
  pollOnce();
  setInterval(pollOnce, Math.max(250, pollIntervalMs));
})();
