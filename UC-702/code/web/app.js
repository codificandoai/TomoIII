// UC-702 — Frontend unificado.
//
// Integra en un solo dashboard, sin dependencias externas ni paso de build,
// funcionalidad inspirada en los proyectos de referencia presentes en /code:
//   - sparkDash (LackOfSkillz/sparkDash): sparklines por métrica, barras de
//     métrica (MetricBar), panel de detalle por nodo (CPU/GPU/Red/Disco) y
//     diálogo de alta de nodo (AddSparkDialog) — aquí sin SSH/exec, solo
//     registro de metadatos contra nuestra propia API.
//   - DGX-Spark-Dashboard: tarjetas de GPU por dispositivo, selector de
//     tema (auto/claro/oscuro) y panel de ajustes con intervalo de refresco.
// Todo el resto (overview de clúster, asignación de pool, vigilancia spot)
// es funcionalidad propia de UC-702 ya existente.

const API_BASE = "";
const HISTORY_LEN = 30;
const DEFAULT_SETTINGS = { refresh_seconds: 5, theme: "auto" };

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

let settings = loadSettings();
let refreshTimer = null;
let lastNodes = [];

// Historial en memoria por nodo/gpu para dibujar sparklines (patrón DGX/sparkDash).
const history = {
  node: new Map(), // node_id -> { cpu: [], memAvailablePct: [], diskAvailablePct: [] }
  gpu: new Map(),  // `${node_id}:${gpu_index}` -> { utilization: [], memFreePct: [] }
};

// ─────────────────────────────────────────────────────────────────────────
// HTTP helpers
// ─────────────────────────────────────────────────────────────────────────
async function apiGet(path) {
  const resp = await fetch(`${API_BASE}${path}`);
  if (!resp.ok) throw new Error(`GET ${path} -> ${resp.status}`);
  return resp.json();
}

async function apiPost(path, body) {
  const resp = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) throw Object.assign(new Error(data.message || `POST ${path} -> ${resp.status}`), { data });
  return data;
}

async function apiDelete(path) {
  const resp = await fetch(`${API_BASE}${path}`, { method: "DELETE" });
  return resp.json().catch(() => ({}));
}

// ─────────────────────────────────────────────────────────────────────────
// Ajustes (tema + intervalo) — persistidos en localStorage, sin backend.
// ─────────────────────────────────────────────────────────────────────────
function loadSettings() {
  try {
    return { ...DEFAULT_SETTINGS, ...JSON.parse(localStorage.getItem("uc702_settings") || "{}") };
  } catch {
    return { ...DEFAULT_SETTINGS };
  }
}

function saveSettings(next) {
  settings = { ...settings, ...next };
  localStorage.setItem("uc702_settings", JSON.stringify(settings));
  applyTheme(settings.theme);
  restartRefreshLoop();
}

function applyTheme(theme) {
  const labels = { auto: "Auto", light: "Claro", dark: "Oscuro" };
  const icons = { auto: "◐", light: "☀", dark: "◑" };
  document.body.dataset.theme = theme;
  $("#theme-label").textContent = labels[theme] || "Auto";
  $("#theme-icon").textContent = icons[theme] || "◐";
}

function cycleTheme() {
  const order = ["auto", "light", "dark"];
  const next = order[(order.indexOf(settings.theme) + 1) % order.length];
  saveSettings({ theme: next });
}

// ─────────────────────────────────────────────────────────────────────────
// Sparklines y barras de métrica (adaptado de DGX-Spark-Dashboard/sparkDash)
// ─────────────────────────────────────────────────────────────────────────
function toneFor(pct) {
  if (pct == null || Number.isNaN(pct)) return "neutral";
  if (pct >= 85) return "danger";
  if (pct >= 60) return "warning";
  return "good";
}

const TONE_COLORS = { good: "#68d391", warning: "#f6ad55", danger: "#fc8181", neutral: "#8b93a7" };

function pushHistory(map, key, field, value) {
  if (!Number.isFinite(value)) return;
  if (!map.has(key)) map.set(key, {});
  const entry = map.get(key);
  if (!entry[field]) entry[field] = [];
  entry[field].push(value);
  if (entry[field].length > HISTORY_LEN) entry[field].shift();
  return entry[field];
}

function sparkline(values, tone = "neutral", width = 90, height = 24) {
  const points = values && values.length ? values : [0, 0];
  const chartPoints = points.length > 1 ? points : [points[0], points[0]];
  const max = Math.max(...chartPoints, 1);
  const color = TONE_COLORS[tone] || TONE_COLORS.neutral;
  const line = chartPoints
    .map((v, i) => {
      const x = (i / (chartPoints.length - 1)) * width;
      const y = height - 2 - Math.min(Math.max(v / max, 0), 1) * (height - 4);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  const area = `0,${height} ${line} ${width},${height}`;
  return `<svg width="${width}" height="${height}" class="sparkline" role="img" aria-hidden="true">
    <polyline points="${area}" fill="${color}" opacity="0.15" stroke="none" />
    <polyline points="${line}" fill="none" stroke="${color}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" />
  </svg>`;
}

function metricBar(label, pct, caption) {
  const clamped = Math.max(0, Math.min(100, pct || 0));
  const tone = toneFor(clamped);
  const color = TONE_COLORS[tone];
  return `<div class="metric-bar">
    <div class="metric-bar-head"><span>${label}</span><span>${caption ?? clamped.toFixed(0) + "%"}</span></div>
    <div class="metric-bar-track"><div class="metric-bar-fill" style="width:${clamped}%;background:${color}"></div></div>
  </div>`;
}

// ─────────────────────────────────────────────────────────────────────────
// Renderizado — overview, tabla de nodos, tarjetas de GPU
// ─────────────────────────────────────────────────────────────────────────
function setConnection(ok) {
  const dot = $("#connection");
  dot.classList.toggle("connected", ok);
  dot.classList.toggle("disconnected", !ok);
}

// ─────────────────────────────────────────────────────────────────────────
// Barra de estado del clúster — inspirada en ClusterSummary de sparkDash:
// de un vistazo responde si el clúster está sano, cuántos nodos están en
// línea y si hay condiciones que requieren atención (nodos "stale", pool sin
// capacidad, interrupciones spot activas).
// ─────────────────────────────────────────────────────────────────────────
function renderStatusBar({ health, summary, nodes, events, allocations }) {
  const total = nodes.length;
  const online = nodes.filter((n) => !n.stale).length;
  const staleCount = total - online;
  const activeAllocations = allocations.filter((a) => !a.released).length;

  let state = "unknown";
  let stateLabel = "Desconocido";
  if (total === 0) {
    state = "unknown";
    stateLabel = "Sin nodos";
  } else if (online === total && staleCount === 0) {
    state = "healthy";
    stateLabel = "Saludable";
  } else if (online > 0) {
    state = "degraded";
    stateLabel = "Degradado";
  } else {
    state = "down";
    stateLabel = "Sin nodos activos";
  }

  const backendOk = !!health;
  const badge = (label, tone) => `<span class="status-badge status-${tone}">${label}</span>`;

  $("#status-bar").innerHTML = `
    <div class="status-identity">
      <span class="status-dot status-dot-${state}"></span>
      <strong>UC-702 Cluster Capacity &amp; Spot Watch</strong>
      ${badge(stateLabel, state === "healthy" ? "ok" : state === "degraded" ? "warn" : "danger")}
      ${backendOk ? badge("API en línea", "ok") : badge("API sin respuesta", "danger")}
      <span class="status-spacer"></span>
      <span class="status-fact">${online}/${total} nodos en línea</span>
    </div>
    <div class="status-facts">
      <div class="status-fact-item"><span class="label">Nodos subutilizados</span><span class="value">${summary.nodes_subutilized ?? 0}</span></div>
      <div class="status-fact-item"><span class="label">CPU disponible</span><span class="value">${(summary.capacity_available?.cpu_cores ?? 0).toFixed(1)} cores</span></div>
      <div class="status-fact-item"><span class="label">Asignaciones activas</span><span class="value">${activeAllocations}</span></div>
      <div class="status-fact-item"><span class="label">Eventos spot</span><span class="value">${events.length}</span></div>
      <div class="status-fact-item"><span class="label">Nodos stale</span><span class="value">${staleCount}</span></div>
    </div>
  `;
}

function renderSummary(summary) {
  const cap = summary.capacity_available || {};
  const cards = [
    { label: "Nodos activos", value: `${summary.nodes_active}/${summary.nodes_total}` },
    { label: "Nodos subutilizados", value: summary.nodes_subutilized },
    { label: "CPU disponible (cores)", value: cap.cpu_cores },
    { label: "Memoria disponible (MB)", value: cap.memory_mb },
    { label: "Disco disponible (GB)", value: cap.disk_gb },
    { label: "GPUs disponibles", value: cap.gpu_count },
  ];
  $("#summary-cards").innerHTML = cards
    .map((c) => `<div class="metric-card"><div class="label">${c.label}</div><div class="value">${c.value ?? "—"}</div></div>`)
    .join("");
}

function renderNodes(nodes) {
  lastNodes = nodes;
  $("#node-count").textContent = `${nodes.length} nodo(s)`;
  if (!nodes.length) {
    $("#nodes-table").innerHTML = "<p>No hay nodos registrados todavía. Use el botón <strong>+ Nodo</strong> o ejecute <code>python UC-702.py agent</code> en cada nodo.</p>";
    return;
  }
  const rows = nodes
    .map((n) => {
      const cap = n.available_capacity || {};
      const snap = n.snapshot || {};
      const cpuIdle = snap.cpu_idle_pct ?? 100 - (snap.cpu_percent ?? 0);
      const memPct = snap.memory_available_pct ?? 0;
      const hist = history.node.get(n.node_id) || {};
      pushHistory(history.node, n.node_id, "cpu", snap.cpu_percent ?? 0);
      pushHistory(history.node, n.node_id, "mem", memPct);
      const badge = n.stale ? '<span class="badge stale">stale</span>' : '<span class="badge">activo</span>';
      return `<tr class="node-row" data-node-id="${n.node_id}">
        <td>${n.node_id}</td>
        <td>${n.platform} / ${n.architecture}</td>
        <td>${n.provider} · ${n.lifecycle}</td>
        <td>${n.site}${n.rack ? " / " + n.rack : ""}</td>
        <td>${sparkline(hist.cpu || [], toneFor(snap.cpu_percent))} ${(snap.cpu_percent ?? 0).toFixed(0)}%</td>
        <td>${cap.cpu_cores_available ?? 0}</td>
        <td>${cap.memory_available_mb ?? 0}</td>
        <td>${cap.gpu_count_available ?? 0}</td>
        <td>${badge}</td>
        <td><button type="button" class="link-btn" data-remove-node="${n.node_id}">quitar</button></td>
      </tr>`;
    })
    .join("");
  $("#nodes-table").innerHTML = `<table>
    <thead><tr><th>Node</th><th>Plataforma</th><th>Proveedor</th><th>Ubicación</th><th>CPU</th><th>CPU libre</th><th>Mem libre (MB)</th><th>GPUs libres</th><th>Estado</th><th></th></tr></thead>
    <tbody>${rows}</tbody>
  </table>`;

  $$(".node-row", $("#nodes-table")).forEach((row) => {
    row.addEventListener("click", (evt) => {
      if (evt.target.closest("[data-remove-node]")) return;
      openNodeModal(row.dataset.nodeId);
    });
  });
  $$("[data-remove-node]", $("#nodes-table")).forEach((btn) => {
    btn.addEventListener("click", async (evt) => {
      evt.stopPropagation();
      await apiDelete(`/api/v1/nodes/${btn.dataset.removeNode}`);
      refreshAll();
    });
  });
}

function renderGpuCards(nodes) {
  const cards = [];
  for (const n of nodes) {
    const gpus = (n.snapshot && n.snapshot.gpus) || [];
    for (const gpu of gpus) {
      const key = `${n.node_id}:${gpu.index}`;
      const util = gpu.utilization_pct;
      const memFreePct = gpu.memory_free_pct;
      if (util != null) pushHistory(history.gpu, key, "util", util);
      const hist = history.gpu.get(key) || {};
      const tone = util == null ? "neutral" : toneFor(util);
      cards.push(`<article class="gpu-card">
        <div class="gpu-card-head">
          <strong>${gpu.name}</strong>
          <span class="badge">${n.node_id}</span>
        </div>
        <div class="gpu-card-usage">
          ${sparkline(hist.util || [], tone, 120, 32)}
          <span class="gpu-usage-value">${util != null ? util.toFixed(0) + "%" : "N/D"}</span>
        </div>
        ${gpu.temperature_c != null ? `<div class="gpu-sub">Temp: ${gpu.temperature_c}°C</div>` : ""}
        ${gpu.power_watts != null ? `<div class="gpu-sub">Potencia: ${gpu.power_watts.toFixed(0)} W</div>` : ""}
        ${gpu.memory_total_mb ? metricBar("VRAM usada", 100 - (memFreePct ?? 0), `${Math.round(gpu.memory_used_mb || 0)} / ${Math.round(gpu.memory_total_mb)} MB`) : `<div class="gpu-sub">VRAM: N/D</div>`}
      </article>`);
    }
  }
  $("#gpu-count").textContent = `${cards.length} GPU(s)`;
  $("#gpu-cards").innerHTML = cards.length
    ? cards.join("")
    : "<p>No se detectaron GPUs en los nodos registrados.</p>";
}

// ─────────────────────────────────────────────────────────────────────────
// Gauge radial — inspirado en Gauge.svelte de dgx-spark-status
// ─────────────────────────────────────────────────────────────────────────
function gauge(value, max = 100, label = "", size = 96, thickness = 9) {
  const pct = Math.max(0, Math.min(100, max > 0 ? (value / max) * 100 : 0));
  const radius = (size - thickness) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (pct / 100) * circumference;
  const center = size / 2;
  const tone = toneFor(pct);
  const color = TONE_COLORS[tone];
  return `<div class="gauge" style="width:${size}px;height:${size}px">
    <svg width="${size}" height="${size}">
      <circle cx="${center}" cy="${center}" r="${radius}" fill="none" stroke="var(--border)" stroke-width="${thickness}" />
      <circle cx="${center}" cy="${center}" r="${radius}" fill="none" stroke="${color}" stroke-width="${thickness}"
        stroke-dasharray="${circumference}" stroke-dashoffset="${offset}" stroke-linecap="round"
        transform="rotate(-90 ${center} ${center})" class="gauge-progress" />
    </svg>
    <div class="gauge-content"><div class="gauge-value">${value.toFixed(0)}${label}</div></div>
  </div>`;
}

// ─────────────────────────────────────────────────────────────────────────
// Asignaciones activas del pool
// ─────────────────────────────────────────────────────────────────────────
function renderAllocations(allocations) {
  if (!allocations.length) {
    $("#allocations-table").innerHTML = "<p>No hay asignaciones activas.</p>";
    return;
  }
  const rows = allocations
    .map((a) => `<tr>
      <td>${a.requester}</td>
      <td>${a.node_id}</td>
      <td>${a.cpu_cores}</td>
      <td>${a.memory_mb}</td>
      <td>${a.gpu_count}</td>
      <td>${a.released ? '<span class="badge stale">liberada</span>' : '<span class="badge">activa</span>'}</td>
      <td>${a.released ? "" : `<button type="button" class="link-btn" data-release="${a.allocation_id}">liberar</button>`}</td>
    </tr>`)
    .join("");
  $("#allocations-table").innerHTML = `<table>
    <thead><tr><th>Requester</th><th>Nodo</th><th>CPU</th><th>Mem (MB)</th><th>GPUs</th><th>Estado</th><th></th></tr></thead>
    <tbody>${rows}</tbody>
  </table>`;
  $$("[data-release]", $("#allocations-table")).forEach((btn) => {
    btn.addEventListener("click", async () => {
      await apiPost("/api/v1/pool/release", { allocation_id: btn.dataset.release });
      refreshAll();
    });
  });
}

// ─────────────────────────────────────────────────────────────────────────
// Analítica de interrupciones spot — inspirada en
// sample-spot-interruption-insights (dashboards OpenSearch por ASG/AZ):
// aquí se agrega por nodo y por proveedor a partir de los eventos ya
// capturados por spot_watcher.py / la API.
// ─────────────────────────────────────────────────────────────────────────
function renderSpotInsights(events) {
  if (!events.length) {
    $("#spot-insights").innerHTML = "<p>Sin datos suficientes todavía. Los eventos se acumulan al detectar interrupciones spot.</p>";
    return;
  }
  const byProvider = {};
  const byNode = {};
  for (const e of events) {
    byProvider[e.provider] = (byProvider[e.provider] || 0) + 1;
    byNode[e.node_id] = (byNode[e.node_id] || 0) + 1;
  }
  const maxProvider = Math.max(...Object.values(byProvider), 1);
  const maxNode = Math.max(...Object.values(byNode), 1);

  const providerBars = Object.entries(byProvider)
    .map(([k, v]) => metricBar(k, (v / maxProvider) * 100, `${v}`))
    .join("");
  const nodeBars = Object.entries(byNode)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)
    .map(([k, v]) => metricBar(k, (v / maxNode) * 100, `${v}`))
    .join("");

  $("#spot-insights").innerHTML = `
    <div class="gpu-sub">Total de interrupciones registradas: <strong>${events.length}</strong></div>
    <h3 class="inline-heading">Por proveedor</h3>
    ${providerBars}
    <h3 class="inline-heading">Por nodo (top 8)</h3>
    ${nodeBars}
  `;
}

// ─────────────────────────────────────────────────────────────────────────
// Dashboards Grafana — catálogo navegable (inspirado en
// grafana-dashboards-kubernetes / gpu-usage-monitor: múltiples dashboards
// JSON empaquetados) con vista y descarga directa desde el dashboard.
// ─────────────────────────────────────────────────────────────────────────
async function loadDashboards() {
  try {
    const resp = await apiGet("/api/v1/dashboards");
    const dashboards = resp.data;
    const rows = Object.entries(dashboards)
      .map(([name, def]) => {
        const panelCount = (def.panels || []).filter((p) => p.type !== "row").length;
        return `<tr>
          <td>${def.title || name}</td>
          <td>${name}</td>
          <td>${panelCount}</td>
          <td>${(def.tags || []).join(", ")}</td>
          <td>
            <button type="button" class="link-btn" data-view-dashboard="${name}">ver JSON</button>
            <button type="button" class="link-btn" data-download-dashboard="${name}">descargar</button>
          </td>
        </tr>`;
      })
      .join("");
    $("#dashboards-list").innerHTML = `<table>
      <thead><tr><th>Título</th><th>Nombre</th><th>Paneles</th><th>Tags</th><th></th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`;

    $$("[data-view-dashboard]", $("#dashboards-list")).forEach((btn) => {
      btn.addEventListener("click", () => {
        const box = $("#dashboard-json");
        box.textContent = JSON.stringify(dashboards[btn.dataset.viewDashboard], null, 2);
        box.classList.remove("hidden");
      });
    });
    $$("[data-download-dashboard]", $("#dashboards-list")).forEach((btn) => {
      btn.addEventListener("click", () => {
        const name = btn.dataset.downloadDashboard;
        const blob = new Blob([JSON.stringify(dashboards[name], null, 2)], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `${name}.json`;
        a.click();
        URL.revokeObjectURL(url);
      });
    });
  } catch (err) {
    $("#dashboards-list").innerHTML = `<p>No se pudieron cargar los dashboards: ${err.message}</p>`;
  }
}

function renderSpotEvents(events) {
  if (!events.length) {
    $("#spot-events").innerHTML = "<p>Sin eventos de interrupción registrados.</p>";
    return;
  }
  const rows = events
    .slice()
    .reverse()
    .map((e) => `<tr><td>${e.node_id}</td><td>${e.provider}</td><td>${e.action}</td><td>${e.detected_at}</td></tr>`)
    .join("");
  $("#spot-events").innerHTML = `<table>
    <thead><tr><th>Nodo</th><th>Proveedor</th><th>Acción</th><th>Detectado</th></tr></thead>
    <tbody>${rows}</tbody>
  </table>`;
}

function renderSchema(schema) {
  const renderCard = (card) => {
    const items = (card.parameters || card.fields || [])
      .map((p) => `<li><code>${p.name}</code> <em>${p.type}</em>${p.required ? " · requerido" : ""}</li>`)
      .join("");
    return `<div class="schema-card"><h3>${card.endpoint}</h3><p>${card.description}</p><ul>${items}</ul></div>`;
  };
  $("#schema-cards").innerHTML = `
    <div><h3>Entradas (Request)</h3>${schema.input_cards.map(renderCard).join("")}</div>
    <div><h3>Salidas (Response)</h3>${schema.output_cards.map(renderCard).join("")}</div>
  `;
}

// ─────────────────────────────────────────────────────────────────────────
// Modal de detalle de nodo — inspirado en SparkPage (CPU/GPU/Red/Disco) de sparkDash
// ─────────────────────────────────────────────────────────────────────────
function openNodeModal(nodeId) {
  const node = lastNodes.find((n) => n.node_id === nodeId);
  if (!node) return;
  const snap = node.snapshot || {};
  const cap = node.available_capacity || {};
  const hist = history.node.get(nodeId) || {};

  $("#node-modal-title").textContent = `Nodo: ${nodeId}`;
  $("#node-modal-body").innerHTML = `
    <div class="detail-grid">
      <section class="panel">
        <h3>CPU</h3>
        <div class="gauge-row">${gauge(snap.cpu_percent ?? 0, 100, "%")}${sparkline(hist.cpu || [], toneFor(snap.cpu_percent), 150, 60)}</div>
        ${metricBar("Uso de CPU", snap.cpu_percent ?? 0)}
        ${metricBar("CPU disponible (idle)", snap.cpu_idle_pct ?? 0)}
        <div class="gpu-sub">${snap.cpu_count_physical ?? "?"} núcleos físicos · ${snap.cpu_count_logical ?? "?"} lógicos · load avg 1m: ${snap.load_avg_1m ?? "N/D"}</div>
        <div class="gpu-sub">Núcleos subutilizados disponibles para el pool: <strong>${cap.cpu_cores_available ?? 0}</strong></div>
      </section>
      <section class="panel">
        <h3>Memoria</h3>
        <div class="gauge-row">${gauge(100 - (snap.memory_available_pct ?? 0), 100, "%")}${sparkline(hist.mem || [], toneFor(100 - (snap.memory_available_pct ?? 0)), 150, 60)}</div>
        ${metricBar("Memoria disponible", snap.memory_available_pct ?? 0, `${Math.round(snap.memory_available_mb ?? 0)} / ${Math.round(snap.memory_total_mb ?? 0)} MB`)}
      </section>
      <section class="panel">
        <h3>Disco</h3>
        ${metricBar("Disco disponible", snap.disk_available_pct ?? 0, `${(snap.disk_free_gb ?? 0).toFixed(1)} / ${(snap.disk_total_gb ?? 0).toFixed(1)} GB`)}
      </section>
      <section class="panel">
        <h3>Red</h3>
        <div class="gpu-sub">↑ ${formatBps(snap.net_sent_rate_bps)} · ↓ ${formatBps(snap.net_recv_rate_bps)}</div>
      </section>
      <section class="panel">
        <h3>GPU</h3>
        ${(snap.gpus || []).length
          ? snap.gpus.map((g) => `
            <div class="gpu-detail-row">
              <strong>${g.name}</strong>
              ${g.utilization_pct != null ? metricBar("Utilización", g.utilization_pct) : '<div class="gpu-sub">Utilización: N/D</div>'}
              ${g.memory_total_mb ? metricBar("VRAM usada", 100 - (g.memory_free_pct ?? 0), `${Math.round(g.memory_used_mb || 0)} / ${Math.round(g.memory_total_mb)} MB`) : '<div class="gpu-sub">VRAM: N/D</div>'}
            </div>`).join("")
          : "<p>Sin GPU detectada.</p>"}
      </section>
    </div>
  `;
  showModal("#node-modal");
}

function formatBps(value = 0) {
  const units = ["bps", "Kbps", "Mbps", "Gbps"];
  let v = value || 0;
  let i = 0;
  while (v >= 1000 && i < units.length - 1) {
    v /= 1000;
    i++;
  }
  return `${v.toFixed(1)} ${units[i]}`;
}

// ─────────────────────────────────────────────────────────────────────────
// Modales genéricos
// ─────────────────────────────────────────────────────────────────────────
function showModal(sel) {
  $(sel).classList.remove("hidden");
}
function hideModal(sel) {
  $(sel).classList.add("hidden");
}
function bindModals() {
  $$("[data-close-modal]").forEach((btn) => {
    btn.addEventListener("click", () => btn.closest(".modal-overlay").classList.add("hidden"));
  });
  $$(".modal-overlay").forEach((overlay) => {
    overlay.addEventListener("click", (evt) => {
      if (evt.target === overlay) overlay.classList.add("hidden");
    });
  });
}

// ─────────────────────────────────────────────────────────────────────────
// Ciclo de refresco
// ─────────────────────────────────────────────────────────────────────────
async function refreshAll() {
  let health = null;
  try {
    health = await apiGet("/health");
  } catch {
    health = null;
  }
  try {
    const [summary, nodes, events, allocations] = await Promise.all([
      apiGet("/api/v1/cluster/summary"),
      apiGet("/api/v1/nodes"),
      apiGet("/api/v1/spot/events"),
      apiGet("/api/v1/pool/allocations"),
    ]);
    renderStatusBar({ health: health?.data, summary: summary.data, nodes: nodes.data, events: events.data, allocations: allocations.data });
    renderSummary(summary.data);
    renderNodes(nodes.data);
    renderGpuCards(nodes.data);
    renderSpotEvents(events.data);
    renderSpotInsights(events.data);
    renderAllocations(allocations.data);
    setConnection(true);
    $("#last-updated").textContent = `Actualizado ${new Date().toLocaleTimeString()}`;
  } catch (err) {
    setConnection(false);
    $("#last-updated").textContent = `Error: ${err.message}`;
  }
}

function restartRefreshLoop() {
  if (refreshTimer) clearInterval(refreshTimer);
  const ms = Math.max(2, Number(settings.refresh_seconds) || 5) * 1000;
  refreshTimer = setInterval(refreshAll, ms);
}

async function loadSchema() {
  try {
    const schema = await apiGet("/api/v1/schema");
    renderSchema(schema.data);
  } catch (err) {
    $("#schema-cards").innerHTML = `<p>No se pudo cargar el esquema: ${err.message}</p>`;
  }
}

// ─────────────────────────────────────────────────────────────────────────
// Formularios
// ─────────────────────────────────────────────────────────────────────────
function bindForms() {
  $("#allocate-form").addEventListener("submit", async (evt) => {
    evt.preventDefault();
    const form = new FormData(evt.target);
    const payload = {
      requester: form.get("requester"),
      cpu_cores: Number(form.get("cpu_cores") || 0),
      memory_mb: Number(form.get("memory_mb") || 0),
      disk_gb: Number(form.get("disk_gb") || 0),
      gpu_count: Number(form.get("gpu_count") || 0),
      gpu_memory_mb: Number(form.get("gpu_memory_mb") || 0),
      preferred_site: form.get("preferred_site") || undefined,
    };
    try {
      const result = await apiPost("/api/v1/pool/allocate", payload);
      $("#allocate-result").textContent = JSON.stringify(result, null, 2);
      refreshAll();
    } catch (err) {
      $("#allocate-result").textContent = JSON.stringify(err.data || { error: err.message }, null, 2);
    }
  });

  $("#spot-form").addEventListener("submit", async (evt) => {
    evt.preventDefault();
    const form = new FormData(evt.target);
    try {
      const result = await apiPost("/api/v1/spot/check", { node_id: form.get("node_id") });
      $("#spot-result").textContent = JSON.stringify(result, null, 2);
      refreshAll();
    } catch (err) {
      $("#spot-result").textContent = JSON.stringify(err.data || { error: err.message }, null, 2);
    }
  });

  $("#add-node-form").addEventListener("submit", async (evt) => {
    evt.preventDefault();
    const form = new FormData(evt.target);
    const payload = Object.fromEntries(form.entries());
    try {
      await apiPost("/api/v1/nodes/register", payload);
      hideModal("#add-node-modal");
      evt.target.reset();
      refreshAll();
    } catch (err) {
      alert(err.data?.message || err.message);
    }
  });

  $("#settings-form").addEventListener("submit", (evt) => {
    evt.preventDefault();
    const form = new FormData(evt.target);
    saveSettings({
      refresh_seconds: Number(form.get("refresh_seconds") || 5),
      theme: form.get("theme") || "auto",
    });
    hideModal("#settings-modal");
  });

  $("#refresh-btn").addEventListener("click", refreshAll);
  $("#theme-switch").addEventListener("click", cycleTheme);
  $("#add-node-btn").addEventListener("click", () => showModal("#add-node-modal"));
  $("#settings-btn").addEventListener("click", () => {
    $("#settings-form [name=refresh_seconds]").value = settings.refresh_seconds;
    $("#settings-form [name=theme]").value = settings.theme;
    showModal("#settings-modal");
  });
}

// ─────────────────────────────────────────────────────────────────────────
// Bootstrap
// ─────────────────────────────────────────────────────────────────────────
applyTheme(settings.theme);
bindModals();
bindForms();
loadSchema();
loadDashboards();
refreshAll();
restartRefreshLoop();
