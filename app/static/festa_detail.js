// festa_detail.js — Dettaglio di una festa: apri/chiudi, prodotti, report.
// L'id festa e' nell'URL: /admin/festa/{id}

"use strict";

const EVENT_ID = parseInt(window.location.pathname.split("/").pop(), 10);
let currentEvent = null;
let productsCache = [];

// ----- Festa -----------------------------------------------------------------

async function loadEvent() {
  try {
    const all = await Admin.getJSON("/api/events");
    currentEvent = all.find(function (e) { return e.id === EVENT_ID; }) || null;
  } catch (e) {
    currentEvent = null;
  }
  renderEventHeader();
}

function renderEventHeader() {
  if (!currentEvent) {
    document.getElementById("event-name").textContent = "Festa non trovata";
    return;
  }
  document.getElementById("event-name").textContent = currentEvent.name;
  document.title = "Festa " + currentEvent.name;
  const status = document.getElementById("event-status");
  status.textContent = currentEvent.active ? "Aperta" : "Chiusa";
  const meta = [];
  if (currentEvent.start_date) meta.push("Data: " + currentEvent.start_date);
  if (currentEvent.note) meta.push(currentEvent.note);
  document.getElementById("event-meta").textContent = meta.join(" — ");

  const toggle = document.getElementById("btn-toggle-open");
  if (currentEvent.active) {
    toggle.textContent = "Chiudi festa";
    toggle.className = "btn btn-small btn-danger";
  } else {
    toggle.textContent = "Apri festa";
    toggle.className = "btn btn-small btn-print";
  }
}

async function deleteEvent() {
  if (!currentEvent) return;
  const msg = currentEvent.active
    ? 'La festa "' + currentEvent.name + '" e\' ancora aperta. Chiudila prima di eliminarla.'
    : 'Eliminare definitivamente la festa "' + currentEvent.name + '"? L\'operazione non e\' reversibile.';
  if (currentEvent.active) { Admin.toast(msg, true); return; }
  if (!confirm(msg)) return;
  try {
    const res = await Admin.fetch("/api/events/" + EVENT_ID, { method: "DELETE" });
    if (!res.ok) { Admin.toast("Errore: " + (await Admin.readError(res)), true); return; }
    Admin.toast("Festa eliminata.", false);
    setTimeout(function () { window.location.href = "/admin/feste"; }, 800);
  } catch (err) { Admin.toast(err.message, true); }
}

async function toggleOpen() {
  if (!currentEvent) return;
  const url = currentEvent.active
    ? "/api/events/" + EVENT_ID + "/close"
    : "/api/events/" + EVENT_ID + "/activate";
  try {
    const res = await Admin.fetch(url, { method: "POST" });
    if (!res.ok) { Admin.toast("Errore: " + (await Admin.readError(res)), true); return; }
    Admin.toast(currentEvent.active ? "Festa chiusa." : "Festa aperta.", false);
    await loadEvent();
    Admin.refreshBadge();
  } catch (err) { Admin.toast(err.message, true); }
}

// ----- Prodotti --------------------------------------------------------------

async function loadProducts() {
  const tbody = document.getElementById("products-tbody");
  try {
    productsCache = await Admin.getJSON("/api/products?event_id=" + EVENT_ID);
    renderProducts();
  } catch (err) {
    tbody.innerHTML = '<tr><td colspan="6">Errore nel caricamento prodotti.</td></tr>';
  }
}

function renderProducts() {
  const tbody = document.getElementById("products-tbody");
  tbody.innerHTML = "";
  if (productsCache.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6">Nessun prodotto. Aggiungine uno.</td></tr>';
    return;
  }
  for (const p of productsCache) {
    const tr = document.createElement("tr");
    // [etichetta, valore]: l'etichetta alimenta il data-label per la vista a
    // schede su telefono (CSS).
    const cells = [
      ["Ordine", p.sort_order],
      ["Nome", p.name],
      ["Categoria", p.category],
      ["Prezzo", Admin.formatEuro(p.price_cents)],
      ["Attivo", p.active ? "Si" : "No"],
    ];
    for (const [labelText, val] of cells) {
      const td = document.createElement("td");
      td.setAttribute("data-label", labelText);
      td.textContent = val;
      tr.appendChild(td);
    }
    const tdActions = document.createElement("td");
    tdActions.setAttribute("data-label", "Azioni");
    const editBtn = document.createElement("button");
    editBtn.type = "button";
    editBtn.className = "btn btn-small";
    editBtn.textContent = "Modifica";
    editBtn.addEventListener("click", function () { openProductModal(p); });
    const delBtn = document.createElement("button");
    delBtn.type = "button";
    delBtn.className = "btn btn-small btn-danger";
    delBtn.textContent = "Elimina";
    delBtn.addEventListener("click", function () { deleteProduct(p); });
    tdActions.appendChild(editBtn);
    tdActions.appendChild(delBtn);
    tr.appendChild(tdActions);
    tbody.appendChild(tr);
  }
}

function openProductModal(p) {
  const title = document.getElementById("product-form-title");
  document.getElementById("product-form").reset();
  if (p) {
    document.getElementById("product-id").value = p.id;
    document.getElementById("p-name").value = p.name;
    document.getElementById("p-category").value = p.category;
    document.getElementById("p-price").value = (p.price_cents / 100).toFixed(2);
    document.getElementById("p-sort").value = p.sort_order;
    document.getElementById("p-active").checked = p.active;
    title.textContent = "Modifica prodotto #" + p.id;
  } else {
    document.getElementById("product-id").value = "";
    document.getElementById("p-active").checked = true;
    title.textContent = "Nuovo prodotto";
  }
  Admin.openModal("product-modal");
}

async function saveProduct(event) {
  event.preventDefault();
  const id = document.getElementById("product-id").value;
  const euros = parseFloat(document.getElementById("p-price").value);
  if (isNaN(euros) || euros < 0) { Admin.toast("Prezzo non valido.", true); return; }
  const body = {
    name: document.getElementById("p-name").value.trim(),
    category: document.getElementById("p-category").value.trim() || "Generale",
    price_cents: Math.round(euros * 100),
    active: document.getElementById("p-active").checked,
    sort_order: parseInt(document.getElementById("p-sort").value, 10) || 0,
    event_id: EVENT_ID,
  };
  if (!body.name) { Admin.toast("Il nome e' obbligatorio.", true); return; }
  const url = id ? "/api/products/" + id : "/api/products";
  const method = id ? "PUT" : "POST";
  try {
    const res = await Admin.fetch(url, {
      method: method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) { Admin.toast("Errore: " + (await Admin.readError(res)), true); return; }
    Admin.toast(id ? "Prodotto aggiornato." : "Prodotto creato.", false);
    Admin.closeModal("product-modal");
    loadProducts();
  } catch (err) { Admin.toast(err.message, true); }
}

async function deleteProduct(p) {
  if (!confirm('Eliminare il prodotto "' + p.name + '"?')) return;
  try {
    const res = await Admin.fetch("/api/products/" + p.id, { method: "DELETE" });
    if (!res.ok) { Admin.toast("Errore: " + (await Admin.readError(res)), true); return; }
    Admin.toast("Prodotto eliminato.", false);
    loadProducts();
  } catch (err) { Admin.toast(err.message, true); }
}

// ----- Dashboard -------------------------------------------------------------

async function loadDashboard() {
  await Promise.all([loadKpisAndProducts(), loadTimeSeries()]);
}

async function loadKpisAndProducts() {
  const chart = document.getElementById("chart-products");
  try {
    const s = await Admin.getJSON("/api/reports/summary?event_id=" + EVENT_ID);
    document.getElementById("kpi-orders").textContent = s.orders_count;
    document.getElementById("kpi-revenue").textContent = Admin.formatEuro(s.total_cents);
    const items = (s.top_products || [])
      .filter(function (p) { return p.qty != null; })
      .map(function (p) { return { label: String(p.product_name), value: p.qty }; });
    renderBarChart(chart, items);
  } catch (err) {
    document.getElementById("kpi-orders").textContent = "—";
    document.getElementById("kpi-revenue").textContent = "—";
    chart.innerHTML = '<p class="hint">Impossibile caricare i dati.</p>';
  }
}

async function loadTimeSeries() {
  const el = document.getElementById("chart-timeseries");
  try {
    const data = await Admin.getJSON("/api/reports/timeseries?event_id=" + EVENT_ID);
    renderTimeSeries(el, data.points || []);
  } catch (err) {
    el.innerHTML = '<p class="hint">Impossibile caricare l\'andamento.</p>';
  }
}

// Grafico a barre orizzontali (qty per prodotto). HTML/CSS, nessuna dipendenza.
function renderBarChart(el, items) {
  if (!items.length) {
    el.innerHTML = '<p class="hint">Nessuna vendita registrata.</p>';
    return;
  }
  const max = items.reduce(function (m, i) { return Math.max(m, i.value); }, 0) || 1;
  el.innerHTML = items.map(function (i) {
    const pct = Math.max(3, Math.round((i.value / max) * 100));
    const name = Admin.escapeHtml(i.label);
    return '<div class="bar-row">' +
      '<span class="bar-label" title="' + name + '">' + name + '</span>' +
      '<span class="bar-track"><span class="bar-fill" style="width:' + pct + '%"></span></span>' +
      '<span class="bar-value">' + i.value + '</span>' +
      '</div>';
  }).join("");
}

// Grafico a linea (ordini per ora). SVG inline, nessuna dipendenza.
function renderTimeSeries(el, points) {
  if (!points.length) {
    el.innerHTML = '<p class="hint">Nessun ordine ancora.</p>';
    return;
  }
  const W = 580, H = 220, padL = 34, padR = 14, padT = 16, padB = 38;
  const innerW = W - padL - padR;
  const innerH = H - padT - padB;
  const n = points.length;
  const maxY = points.reduce(function (m, p) { return Math.max(m, p.orders); }, 0) || 1;

  const xAt = function (i) { return n === 1 ? padL + innerW / 2 : padL + (innerW * i) / (n - 1); };
  const yAt = function (v) { return padT + innerH * (1 - v / maxY); };
  const label = function (p) { return (p.bucket || "").slice(11, 16); };

  const coords = points.map(function (p, i) { return [xAt(i), yAt(p.orders)]; });
  const line = coords.map(function (c, i) { return (i ? "L" : "M") + c[0] + " " + c[1]; }).join(" ");
  const area = "M" + xAt(0) + " " + yAt(0) + " " +
    coords.map(function (c) { return "L" + c[0] + " " + c[1]; }).join(" ") +
    " L" + xAt(n - 1) + " " + yAt(0) + " Z";

  // Etichette X: prima, una intermedia, ultima (evita sovrapposizioni).
  const idxs = n <= 3 ? points.map(function (_, i) { return i; })
    : [0, Math.floor((n - 1) / 2), n - 1];
  const xLabels = idxs.map(function (i) {
    return '<text x="' + xAt(i) + '" y="' + (H - 14) + '" class="ts-xlabel">' +
      Admin.escapeHtml(label(points[i])) + "</text>";
  }).join("");

  const dots = coords.map(function (c, i) {
    return '<circle cx="' + c[0] + '" cy="' + c[1] + '" r="3.5" class="ts-dot">' +
      "<title>" + Admin.escapeHtml(label(points[i])) + " — " + points[i].orders +
      " ordini</title></circle>";
  }).join("");

  el.innerHTML =
    '<svg viewBox="0 0 ' + W + " " + H + '" class="ts-svg" preserveAspectRatio="xMidYMid meet" role="img" ' +
    'aria-label="Andamento ordini nel tempo">' +
    // griglia: base (0) e massimo
    '<line x1="' + padL + '" y1="' + yAt(0) + '" x2="' + (W - padR) + '" y2="' + yAt(0) + '" class="ts-axis"/>' +
    '<line x1="' + padL + '" y1="' + yAt(maxY) + '" x2="' + (W - padR) + '" y2="' + yAt(maxY) + '" class="ts-grid"/>' +
    '<text x="' + (padL - 6) + '" y="' + (yAt(maxY) + 4) + '" class="ts-ylabel">' + maxY + "</text>" +
    '<text x="' + (padL - 6) + '" y="' + (yAt(0) + 4) + '" class="ts-ylabel">0</text>' +
    '<path d="' + area + '" class="ts-area"/>' +
    '<path d="' + line + '" class="ts-line"/>' +
    dots + xLabels +
    "</svg>";
}

// ----- Init ------------------------------------------------------------------

function initPage() {
  if (isNaN(EVENT_ID)) {
    document.getElementById("event-name").textContent = "Festa non valida";
    return;
  }
  loadEvent();
  loadProducts();
  loadDashboard();
  document.getElementById("btn-toggle-open").addEventListener("click", toggleOpen);
  document.getElementById("btn-delete-event").addEventListener("click", deleteEvent);
  document.getElementById("btn-new-product").addEventListener("click", function () {
    openProductModal(null);
  });
  document.getElementById("p-cancel").addEventListener("click", function () {
    Admin.closeModal("product-modal");
  });
  document.getElementById("product-form").addEventListener("submit", saveProduct);
  document.getElementById("btn-refresh-summary").addEventListener("click", loadDashboard);
}

Admin.ready(initPage);
