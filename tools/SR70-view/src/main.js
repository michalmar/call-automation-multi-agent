import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "./styles.css";

const collator = new Intl.Collator("cs", { sensitivity: "base", numeric: true });
const app = document.querySelector("#app");
app.innerHTML = `<div class="empty-state empty-state--loading">Loading station atlas…</div>`;

const stations = await loadStations();

const qualifierTheme = {
  "Železniční stanice": "station",
  Zastávka: "stop",
};

const state = {
  query: "",
  region: "all",
  status: "all",
  operator: "all",
  qualifier: "all",
  activeOnly: false,
  sortKey: "name",
  sortDirection: "asc",
  selectedId: stations.find((station) => station.status === "Aktivní")?.id ?? stations[0]?.id ?? null,
};

const selectOptions = {
  regions: uniqueValues(stations, "region"),
  statuses: uniqueValues(stations, "status"),
  operators: uniqueValues(stations, "operator"),
  qualifiers: uniqueValues(stations, "qualifierLabel"),
};

const mapState = {
  map: null,
  filteredLayer: null,
  selectedLayer: null,
  markerById: new Map(),
};

renderShell();
render();

async function loadStations() {
  const response = await fetch("/data/stations.json", { cache: "no-store" });
  if (!response.ok) {
    app.innerHTML = `<div class="empty-state">Failed to load station data.</div>`;
    throw new Error(`Station data request failed with ${response.status}`);
  }

  const payload = await response.json();
  if (!Array.isArray(payload) || !payload.length) {
    app.innerHTML = `<div class="empty-state">Station data is empty.</div>`;
    throw new Error("Station data payload is empty.");
  }
  return payload;
}

function uniqueValues(items, key) {
  return [...new Set(items.map((item) => item[key]).filter(Boolean))].sort(collator.compare);
}

function normalizeSearch(value) {
  return value
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase();
}

function filterStations() {
  const search = normalizeSearch(state.query.trim());
  return stations.filter((station) => {
    if (state.region !== "all" && station.region !== state.region) return false;
    if (state.status !== "all" && station.status !== state.status) return false;
    if (state.operator !== "all" && station.operator !== state.operator) return false;
    if (state.qualifier !== "all" && station.qualifierLabel !== state.qualifier) return false;
    if (state.activeOnly && station.status !== "Aktivní") return false;
    if (!search) return true;

    const haystack = normalizeSearch(
      [
        station.name,
        station.displayName,
        station.foreignName,
        station.region,
        station.operator,
        station.node,
        station.id,
      ]
        .filter(Boolean)
        .join(" "),
    );
    return haystack.includes(search);
  });
}

function sortStations(items) {
  const sorted = [...items];
  sorted.sort((left, right) => {
    const multiplier = state.sortDirection === "asc" ? 1 : -1;
    const leftValue = left[state.sortKey];
    const rightValue = right[state.sortKey];

    if (typeof leftValue === "number" && typeof rightValue === "number") {
      return (leftValue - rightValue) * multiplier;
    }
    return collator.compare(String(leftValue ?? ""), String(rightValue ?? "")) * multiplier;
  });
  return sorted;
}

function currentSelection(items) {
  const selected = items.find((station) => station.id === state.selectedId);
  if (selected) return selected;
  if (items[0]) {
    state.selectedId = items[0].id;
    return items[0];
  }
  state.selectedId = null;
  return null;
}

function summarize(items) {
  const active = items.filter((station) => station.status === "Aktivní").length;
  const stationsOnly = items.filter((station) => station.qualifierCode === "1").length;
  const stopsOnly = items.filter((station) => station.qualifierCode === "61").length;
  const operator = mostCommon(items, "operator");
  return { active, stationsOnly, stopsOnly, operator };
}

function mostCommon(items, key) {
  const counts = new Map();
  for (const item of items) {
    counts.set(item[key], (counts.get(item[key]) ?? 0) + 1);
  }
  return [...counts.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] ?? "—";
}

function formatNumber(value, digits = 0) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return new Intl.NumberFormat("cs-CZ", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value);
}

function renderShell() {
  app.innerHTML = `
    <div class="chrome">
      <div class="chrome__glow chrome__glow--left"></div>
      <div class="chrome__glow chrome__glow--right"></div>
      <header class="hero">
        <div class="hero__meta">
          <span class="eyebrow">Správa železnic / Atlas</span>
          <span class="pill">Built from SR70 lookup data</span>
        </div>
        <div class="hero__title">
          <div>
            <h1>Czech Rail Atlas</h1>
            <p>
              A live operational view of Czech railway stations and stops filtered from the official
              registry by <strong>Kvalifikátor 1</strong> and <strong>61</strong>.
            </p>
          </div>
          <div class="hero__badge">
            <span>Operational cartography</span>
            <strong>2,448 nodes</strong>
          </div>
        </div>
      </header>

      <main class="layout">
        <section class="panel panel--filters">
          <div class="panel__header">
            <span class="panel__kicker">Control deck</span>
            <h2>Filter the network</h2>
          </div>
          <div class="controls">
            <label class="field field--search">
              <span>Search</span>
              <input id="query" type="search" placeholder="Station, region, operator, code…" />
            </label>
            <label class="field">
              <span>Region</span>
              <select id="region"></select>
            </label>
            <label class="field">
              <span>Status</span>
              <select id="status"></select>
            </label>
            <label class="field">
              <span>Operator</span>
              <select id="operator"></select>
            </label>
            <label class="field">
              <span>Type</span>
              <select id="qualifier"></select>
            </label>
            <label class="toggle">
              <input id="activeOnly" type="checkbox" />
              <span>Active locations only</span>
            </label>
            <div class="actions">
              <button id="clearFilters" class="button button--ghost">Reset filters</button>
              <button id="fitVisible" class="button">Fit visible map</button>
            </div>
          </div>
          <div id="statCards" class="stats"></div>
        </section>

        <section class="panel panel--map">
          <div class="panel__header panel__header--dense">
            <div>
              <span class="panel__kicker">Spatial view</span>
              <h2>Network map</h2>
            </div>
            <div id="resultMeta" class="result-meta"></div>
          </div>
          <div id="map" class="map"></div>
        </section>

        <aside class="panel panel--detail">
          <div class="panel__header">
            <span class="panel__kicker">Selected node</span>
            <h2>Station dossier</h2>
          </div>
          <div id="detailCard" class="detail-card"></div>
        </aside>

        <section class="panel panel--table">
          <div class="panel__header panel__header--dense">
            <div>
              <span class="panel__kicker">Registry list</span>
              <h2>Stations table</h2>
            </div>
            <div class="table-legend">
              <span><i class="swatch swatch--station"></i> Station</span>
              <span><i class="swatch swatch--stop"></i> Stop</span>
            </div>
          </div>
          <div class="table-wrap">
            <table class="data-table">
              <thead>
                <tr>
                  <th data-sort="name">Name</th>
                  <th data-sort="qualifierLabel">Type</th>
                  <th data-sort="status">Status</th>
                  <th data-sort="region">Region</th>
                  <th data-sort="operator">Operator</th>
                  <th data-sort="kmPosition">Km</th>
                </tr>
              </thead>
              <tbody id="tableBody"></tbody>
            </table>
          </div>
        </section>
      </main>
    </div>
  `;

  populateSelect("region", "All regions", selectOptions.regions);
  populateSelect("status", "All statuses", selectOptions.statuses);
  populateSelect("operator", "All operators", selectOptions.operators);
  populateSelect("qualifier", "All types", selectOptions.qualifiers);

  document.querySelector("#query").addEventListener("input", (event) => {
    state.query = event.target.value;
    render();
  });
  document.querySelector("#region").addEventListener("change", (event) => {
    state.region = event.target.value;
    render();
  });
  document.querySelector("#status").addEventListener("change", (event) => {
    state.status = event.target.value;
    render();
  });
  document.querySelector("#operator").addEventListener("change", (event) => {
    state.operator = event.target.value;
    render();
  });
  document.querySelector("#qualifier").addEventListener("change", (event) => {
    state.qualifier = event.target.value;
    render();
  });
  document.querySelector("#activeOnly").addEventListener("change", (event) => {
    state.activeOnly = event.target.checked;
    render();
  });
  document.querySelector("#clearFilters").addEventListener("click", () => {
    state.query = "";
    state.region = "all";
    state.status = "all";
    state.operator = "all";
    state.qualifier = "all";
    state.activeOnly = false;
    syncControls();
    render();
  });
  document.querySelector("#fitVisible").addEventListener("click", () => {
    const items = sortStations(filterStations());
    fitToStations(items);
  });

  document.querySelectorAll("th[data-sort]").forEach((header) => {
    header.addEventListener("click", () => {
      const { sort } = header.dataset;
      if (state.sortKey === sort) {
        state.sortDirection = state.sortDirection === "asc" ? "desc" : "asc";
      } else {
        state.sortKey = sort;
        state.sortDirection = sort === "kmPosition" ? "asc" : "asc";
      }
      render();
    });
  });

  initializeMap();
  syncControls();
}

function populateSelect(id, label, values) {
  const select = document.querySelector(`#${id}`);
  select.innerHTML = `<option value="all">${label}</option>${values
    .map((value) => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`)
    .join("")}`;
}

function syncControls() {
  document.querySelector("#query").value = state.query;
  document.querySelector("#region").value = state.region;
  document.querySelector("#status").value = state.status;
  document.querySelector("#operator").value = state.operator;
  document.querySelector("#qualifier").value = state.qualifier;
  document.querySelector("#activeOnly").checked = state.activeOnly;
}

function render() {
  const filtered = sortStations(filterStations());
  const selected = currentSelection(filtered);
  const stats = summarize(filtered);

  renderStats(filtered, stats);
  renderResultMeta(filtered);
  renderDetails(selected);
  renderTable(filtered, selected);
  renderMap(filtered, selected);
  syncSortIndicators();
}

function renderStats(items, stats) {
  const target = document.querySelector("#statCards");
  target.innerHTML = `
    <article class="stat-card">
      <span>Visible locations</span>
      <strong>${formatNumber(items.length)}</strong>
    </article>
    <article class="stat-card">
      <span>Active</span>
      <strong>${formatNumber(stats.active)}</strong>
    </article>
    <article class="stat-card">
      <span>Stations / Stops</span>
      <strong>${formatNumber(stats.stationsOnly)} / ${formatNumber(stats.stopsOnly)}</strong>
    </article>
    <article class="stat-card">
      <span>Lead operator</span>
      <strong>${escapeHtml(stats.operator)}</strong>
    </article>
  `;
}

function renderResultMeta(items) {
  const target = document.querySelector("#resultMeta");
  target.textContent = `${formatNumber(items.length)} visible • sorted by ${state.sortKey}`;
}

function renderDetails(station) {
  const target = document.querySelector("#detailCard");
  if (!station) {
    target.innerHTML = `<div class="empty-state">No stations match the current filter.</div>`;
    return;
  }

  target.innerHTML = `
    <div class="detail-card__top">
      <div>
        <span class="tag tag--${qualifierTheme[station.qualifierLabel] ?? "station"}">${escapeHtml(
          station.qualifierLabel,
        )}</span>
        <h3>${escapeHtml(station.name)}</h3>
        <p>${escapeHtml(station.region)} • ${escapeHtml(station.status)}</p>
      </div>
      <div class="id-chip">#${escapeHtml(station.id)}</div>
    </div>
    <dl class="detail-grid">
      <div><dt>Operator</dt><dd>${escapeHtml(station.operator ?? "—")}</dd></div>
      <div><dt>Owner</dt><dd>${escapeHtml(station.owner ?? "—")}</dd></div>
      <div><dt>Kilometre</dt><dd>${formatNumber(station.kmPosition, 3)}</dd></div>
      <div><dt>Elevation</dt><dd>${formatNumber(station.elevation, 0)} m</dd></div>
      <div><dt>Node</dt><dd>${escapeHtml(station.node ?? "—")}</dd></div>
      <div><dt>District</dt><dd>${escapeHtml(station.operatingDistrict ?? "—")}</dd></div>
      <div><dt>Directorate</dt><dd>${escapeHtml(station.directorate ?? "—")}</dd></div>
      <div><dt>Remote control</dt><dd>${escapeHtml(station.remoteControl ?? "—")}</dd></div>
      <div><dt>Coordinates</dt><dd>${station.lat.toFixed(4)}, ${station.lng.toFixed(4)}</dd></div>
      <div><dt>TUDU / TTP</dt><dd>${escapeHtml(station.tudu ?? "—")} / ${escapeHtml(
        station.ttp ?? "—",
      )}</dd></div>
    </dl>
    <div class="detail-card__footer">
      <button id="zoomSelected" class="button">Zoom to station</button>
    </div>
  `;

  document.querySelector("#zoomSelected").addEventListener("click", () => {
    if (mapState.map) {
      mapState.map.flyTo([station.lat, station.lng], 12, { duration: 0.85 });
    }
  });
}

function renderTable(items, selected) {
  const body = document.querySelector("#tableBody");
  body.innerHTML = "";
  const fragment = document.createDocumentFragment();

  for (const station of items) {
    const row = document.createElement("tr");
    row.className = `${station.id === selected?.id ? "is-selected" : ""}`;
    row.innerHTML = `
      <td>
        <button class="row-link" data-id="${escapeHtml(station.id)}">
          <span>${escapeHtml(station.name)}</span>
          <small>${escapeHtml(station.id)}</small>
        </button>
      </td>
      <td><span class="tag tag--${qualifierTheme[station.qualifierLabel] ?? "station"}">${escapeHtml(
        station.qualifierLabel,
      )}</span></td>
      <td>${escapeHtml(station.status)}</td>
      <td>${escapeHtml(station.region)}</td>
      <td>${escapeHtml(station.operator)}</td>
      <td>${formatNumber(station.kmPosition, 3)}</td>
    `;
    fragment.appendChild(row);
  }

  body.appendChild(fragment);
  body.querySelectorAll(".row-link").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedId = button.dataset.id;
      render();
    });
  });
}

function initializeMap() {
  mapState.map = L.map("map", {
    zoomControl: false,
    preferCanvas: true,
  }).setView([49.82, 15.45], 8);

  L.control
    .zoom({
      position: "bottomright",
    })
    .addTo(mapState.map);

  L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
    attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
    subdomains: "abcd",
    maxZoom: 19,
  }).addTo(mapState.map);

  mapState.filteredLayer = L.layerGroup().addTo(mapState.map);
  mapState.selectedLayer = L.layerGroup().addTo(mapState.map);
}

function renderMap(items, selected) {
  mapState.filteredLayer.clearLayers();
  mapState.selectedLayer.clearLayers();
  mapState.markerById.clear();

  for (const station of items) {
    const marker = L.circleMarker([station.lat, station.lng], {
      radius: station.id === selected?.id ? 7 : 4.25,
      weight: station.id === selected?.id ? 2 : 1,
      color: station.qualifierCode === "1" ? "#f6c760" : "#6ae2ff",
      fillColor: station.qualifierCode === "1" ? "#f6c760" : "#6ae2ff",
      fillOpacity: station.status === "Aktivní" ? 0.9 : 0.42,
      opacity: 0.95,
    });
    marker.on("click", () => {
      state.selectedId = station.id;
      render();
    });
    marker.bindTooltip(
      `${station.name}<br><span>${station.qualifierLabel} • ${station.status}</span>`,
      { direction: "top" },
    );
    marker.addTo(mapState.filteredLayer);
    mapState.markerById.set(station.id, marker);
  }

  if (selected) {
    L.circleMarker([selected.lat, selected.lng], {
      radius: 14,
      weight: 1,
      color: "#fff4ca",
      fillOpacity: 0,
      opacity: 0.85,
      dashArray: "4 6",
    }).addTo(mapState.selectedLayer);
  }
}

function fitToStations(items) {
  if (!mapState.map || !items.length) return;
  if (items.length === 1) {
    mapState.map.flyTo([items[0].lat, items[0].lng], 12, { duration: 0.85 });
    return;
  }

  const bounds = L.latLngBounds(items.map((item) => [item.lat, item.lng]));
  mapState.map.fitBounds(bounds, {
    padding: [30, 30],
    maxZoom: 11,
  });
}

function syncSortIndicators() {
  document.querySelectorAll("th[data-sort]").forEach((header) => {
    header.classList.toggle("is-active", header.dataset.sort === state.sortKey);
    header.dataset.direction = header.dataset.sort === state.sortKey ? state.sortDirection : "";
  });
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}
