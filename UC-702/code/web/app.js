// UC-702 — Frontend unificado: overview de clúster, nodos, asignación de
// capacidad del pool y vigilancia de interrupción de instancias spot.
// Vanilla JS, sin dependencias externas ni paso de build.

const API_BASE = "";
const REFRESH_MS = 5000;

const $ = (sel) => document.querySelector(sel);

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

function setConnection(ok) {
  const dot = $("#connection");
  dot.classList.toggle("connected", ok);
  dot.classList.toggle("disconnected", !ok);
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
  $("#node-count").textContent = `${nodes.length} nodo(s)`;
  if (!nodes.length) {
    $("#nodes-table").innerHTML = "<p>No hay nodos registrados todavía. Ejecute <code>python UC-702.py agent</code> en cada nodo.</p>";
    return;
  }
  const rows = nodes
    .map((n) => {
      const cap = n.available_capacity || {};
      const snap = n.snapshot || {};
      const badge = n.stale ? '<span class="badge stale">stale</span>' : '<span class="badge">activo</span>';
      return `<tr>
        <td>${n.node_id}</td>
        <td>${n.platform} / ${n.architecture}</td>
        <td>${n.provider} · ${n.lifecycle}</td>
        <td>${n.site}${n.rack ? " / " + n.rack : ""}</td>
        <td>${snap.cpu_percent ?? "—"}%</td>
        <td>${cap.cpu_cores_available ?? 0}</td>
        <td>${cap.memory_available_mb ?? 0}</td>
        <td>${cap.gpu_count_available ?? 0}</td>
        <td>${badge}</td>
      </tr>`;
    })
    .join("");
  $("#nodes-table").innerHTML = `<table>
    <thead><tr><th>Node</th><th>Plataforma</th><th>Proveedor</th><th>Ubicación</th><th>CPU %</th><th>CPU libre</th><th>Mem libre (MB)</th><th>GPUs libres</th><th>Estado</th></tr></thead>
    <tbody>${rows}</tbody>
  </table>`;
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
  const renderCard = (card, kind) => {
    const items = (card.parameters || card.fields || [])
      .map((p) => `<li><code>${p.name}</code> <em>${p.type}</em>${p.required ? " · requerido" : ""}</li>`)
      .join("");
    return `<div class="schema-card"><h3>${card.endpoint}</h3><p>${card.description}</p><ul>${items}</ul></div>`;
  };
  const inputHtml = schema.input_cards.map((c) => renderCard(c, "input")).join("");
  const outputHtml = schema.output_cards.map((c) => renderCard(c, "output")).join("");
  $("#schema-cards").innerHTML = `
    <div><h3>Entradas (Request)</h3>${inputHtml}</div>
    <div><h3>Salidas (Response)</h3>${outputHtml}</div>
  `;
}

async function refreshAll() {
  try {
    const [summary, nodes, events] = await Promise.all([
      apiGet("/api/v1/cluster/summary"),
      apiGet("/api/v1/nodes"),
      apiGet("/api/v1/spot/events"),
    ]);
    renderSummary(summary.data);
    renderNodes(nodes.data);
    renderSpotEvents(events.data);
    setConnection(true);
    $("#last-updated").textContent = `Actualizado ${new Date().toLocaleTimeString()}`;
  } catch (err) {
    setConnection(false);
    $("#last-updated").textContent = `Error: ${err.message}`;
  }
}

async function loadSchema() {
  try {
    const schema = await apiGet("/api/v1/schema");
    renderSchema(schema.data);
  } catch (err) {
    $("#schema-cards").innerHTML = `<p>No se pudo cargar el esquema: ${err.message}</p>`;
  }
}

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

  $("#refresh-btn").addEventListener("click", refreshAll);
}

bindForms();
loadSchema();
refreshAll();
setInterval(refreshAll, REFRESH_MS);
