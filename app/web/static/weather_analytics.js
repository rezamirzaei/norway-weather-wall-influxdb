(() => {
  const root = document.getElementById("weather-analytics");
  if (!root) return;

  const summaryUrl = root.dataset.summaryUrl || "/ui/weather/temperature/summary.json?hours=24";
  const trendUrl = root.dataset.trendUrl || "/ui/weather/temperature/trend.json?hours=1&window_seconds=60";
  const refreshMs = Number(root.dataset.refreshMs || 15000);

  const summaryBody = document.getElementById("weather-summary-body");
  const chartCanvas = document.getElementById("weather-trend-chart");

  const esc = (v) =>
    String(v ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");

  const fmtNum = (v, digits = 1) => {
    if (v === null || v === undefined || v === "") return "—";
    const n = Number(v);
    if (!Number.isFinite(n)) return "—";
    return n.toFixed(digits);
  };

  const renderSummary = (rows) => {
    if (!summaryBody) return;
    const arr = Array.isArray(rows) ? rows : [];
    arr.sort((a, b) => String(a.city).localeCompare(String(b.city)));
    if (!arr.length) {
      summaryBody.innerHTML =
        '<tr><td colspan="6" class="muted">No data yet.</td></tr>';
      return;
    }
    summaryBody.innerHTML = arr
      .map(
        (r) => `
        <tr>
          <td>${esc(r.city)}</td>
          <td>${esc(fmtNum(r.min))}</td>
          <td>${esc(fmtNum(r.avg))}</td>
          <td>${esc(fmtNum(r.max))}</td>
          <td>${esc(fmtNum(r.first))}</td>
          <td>${esc(fmtNum(r.last))}</td>
        </tr>`
      )
      .join("");
  };

  const colors = ["#4dabf7", "#51cf66", "#fcc419", "#ff6b6b", "#845ef7"];
  let chart = null;

  const upsertTrendChart = (points) => {
    if (!chartCanvas || typeof Chart === "undefined") return;
    const arr = Array.isArray(points) ? points : [];
    if (!arr.length) return;

    const timestamps = [...new Set(arr.map((p) => String(p.timestamp)))].sort();
    const labels = timestamps.map((ts) => ts.slice(11, 16));
    const indexByTs = new Map(timestamps.map((t, i) => [t, i]));

    const byCity = new Map();
    arr.forEach((p) => {
      const city = String(p.city ?? "");
      const ts = String(p.timestamp ?? "");
      const i = indexByTs.get(ts);
      const v = Number(p.value);
      if (!city || i === undefined || !Number.isFinite(v)) return;
      if (!byCity.has(city)) byCity.set(city, new Array(labels.length).fill(null));
      byCity.get(city)[i] = v;
    });

    const datasets = [...byCity.entries()].map(([city, data], i) => {
      const c = colors[i % colors.length];
      return {
        label: city,
        data,
        borderColor: c,
        backgroundColor: c,
        borderWidth: 2,
        pointRadius: 0,
        tension: 0.25,
        spanGaps: true,
      };
    });

    if (!chart) {
      chart = new Chart(chartCanvas, {
        type: "line",
        data: { labels, datasets },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          animation: false,
          plugins: {
            legend: { display: true, labels: { color: "#eef2ff" } },
            tooltip: { intersect: false, mode: "index" },
          },
          scales: {
            x: {
              ticks: { color: "#9aa6c0", maxTicksLimit: 8 },
              grid: { color: "rgba(34, 48, 90, 0.4)" },
            },
            y: {
              ticks: { color: "#9aa6c0" },
              grid: { color: "rgba(34, 48, 90, 0.4)" },
              title: { display: true, text: "°C", color: "#9aa6c0" },
            },
          },
        },
      });
      return;
    }

    chart.data.labels = labels;
    chart.data.datasets = datasets;
    chart.update("none");
  };

  let inFlight = false;
  const poll = async () => {
    if (inFlight) return;
    inFlight = true;
    try {
      const [summaryResp, trendResp] = await Promise.all([
        fetch(summaryUrl, { headers: { Accept: "application/json" }, cache: "no-store" }),
        fetch(trendUrl, { headers: { Accept: "application/json" }, cache: "no-store" }),
      ]);
      if (!summaryResp.ok) throw new Error(`summary HTTP ${summaryResp.status}`);
      if (!trendResp.ok) throw new Error(`trend HTTP ${trendResp.status}`);
      const [summary, trend] = await Promise.all([summaryResp.json(), trendResp.json()]);
      renderSummary(summary);
      upsertTrendChart(trend);
    } catch (_err) {
      // Keep last known UI; failures are common if Influx isn't up yet.
    } finally {
      inFlight = false;
    }
  };

  poll();
  setInterval(poll, Math.max(3000, refreshMs));
})();

