// admin.js — Logica dell'area gestione (JS vanilla).
// Gestisce: sblocco con PIN, FESTE (crea/attiva/elimina), PRODOTTI per festa,
// MAGAZZINO (scollegato dalla cassa), configurazione, report e manutenzione.
// Le chiamate "admin" inviano l'header X-Admin-Pin; un 401 fa ricomparire la
// schermata di sblocco.

"use strict";

const PIN_KEY = "festa_admin_pin";

// ---------------------------------------------------------------------------
// Utility
// ---------------------------------------------------------------------------

function formatEuro(cents) {
  return (cents / 100).toFixed(2) + " €";
}

function getPin() { return sessionStorage.getItem(PIN_KEY) || ""; }
function setPin(pin) { sessionStorage.setItem(PIN_KEY, pin); }
function clearPin() { sessionStorage.removeItem(PIN_KEY); }

function showToast(message, isError) {
  const toast = document.getElementById("toast");
  toast.textContent = message;
  toast.className = "toast show" + (isError ? " error" : "");
  clearTimeout(showToast._timer);
  showToast._timer = setTimeout(function () { toast.className = "toast"; }, 3500);
}

async function readError(res) {
  try {
    const data = await res.json();
    if (data && data.detail) {
      if (typeof data.detail === "string") return data.detail;
      return JSON.stringify(data.detail);
    }
  } catch (e) { /* corpo non JSON */ }
  return "HTTP " + res.status;
}

function escapeHtml(str) {
  return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

// Wrapper fetch per le chiamate admin: aggiunge X-Admin-Pin e gestisce il 401.
async function adminFetch(url, options) {
  options = options || {};
  options.headers = Object.assign({}, options.headers, { "X-Admin-Pin": getPin() });
  const res = await fetch(url, options);
  if (res.status === 401) {
    handleUnauthorized();
    throw new Error("PIN errato o mancante.");
  }
  return res;
}

// ---------------------------------------------------------------------------
// Sblocco / blocco
// ---------------------------------------------------------------------------

function showGate() {
  document.getElementById("pin-gate").classList.remove("hidden");
  document.getElementById("admin-content").classList.add("hidden");
}

function showContent() {
  document.getElementById("pin-gate").classList.add("hidden");
  document.getElementById("admin-content").classList.remove("hidden");
}

function handleUnauthorized() {
  clearPin();
  const errEl = document.getElementById("pin-error");
  errEl.textContent = "PIN errato. Riprova.";
  errEl.classList.remove("hidden");
  showGate();
}

async function tryUnlock() {
  const pin = document.getElementById("pin-input").value.trim();
  if (!pin) return;
  setPin(pin);
  try {
    // PUT con corpo vuoto: non modifica nulla ma richiede PIN valido.
    const res = await adminFetch("/api/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    if (!res.ok) {
      showToast("Errore: " + (await readError(res)), true);
      return;
    }
    document.getElementById("pin-error").classList.add("hidden");
    document.getElementById("pin-input").value = "";
    showContent();
    initContent();
  } catch (err) {
    // adminFetch ha gia' gestito il 401.
  }
}

// ---------------------------------------------------------------------------
// Stato condiviso
// ---------------------------------------------------------------------------

let eventsCache = [];        // tutte le feste
let activeEventId = null;    // id festa attiva
let selectedEventId = null;  // festa selezionata nella sezione Prodotti

// ---------------------------------------------------------------------------
// FESTE
// ---------------------------------------------------------------------------

async function loadEvents() {
  const tbody = document.getElementById("events-tbody");
  try {
    const res = await fetch("/api/events");
    if (!res.ok) throw new Error("HTTP " + res.status);
    eventsCache = await res.json();
    const active = eventsCache.find(function (e) { return e.active; });
    activeEventId = active ? active.id : null;
    if (selectedEventId === null) selectedEventId = activeEventId;
    renderEventsTable();
    renderProductEventSelect();
    renderActiveBadge();
  } catch (err) {
    tbody.innerHTML = '<tr><td colspan="5">Errore nel caricamento feste.</td></tr>';
  }
}

function renderActiveBadge() {
  const badge = document.getElementById("active-event-badge");
  const active = eventsCache.find(function (e) { return e.active; });
  if (active) {
    badge.textContent = "Festa attiva: " + active.name;
    badge.classList.remove("hidden");
  } else {
    badge.textContent = "Nessuna festa attiva";
    badge.classList.remove("hidden");
  }
}

function renderEventsTable() {
  const tbody = document.getElementById("events-tbody");
  tbody.innerHTML = "";
  if (eventsCache.length === 0) {
    tbody.innerHTML = '<tr><td colspan="5">Nessuna festa. Creane una qui sotto.</td></tr>';
    return;
  }
  for (const ev of eventsCache) {
    const tr = document.createElement("tr");
    if (ev.active) tr.className = "row-active";

    const tdState = document.createElement("td");
    tdState.textContent = ev.active ? "● ATTIVA" : "—";

    const tdName = document.createElement("td");
    tdName.textContent = ev.name;

    const tdDate = document.createElement("td");
    tdDate.textContent = ev.start_date || "";

    const tdNote = document.createElement("td");
    tdNote.textContent = ev.note || "";

    const tdActions = document.createElement("td");
    if (!ev.active) {
      const actBtn = document.createElement("button");
      actBtn.type = "button";
      actBtn.className = "btn btn-small btn-print";
      actBtn.textContent = "Attiva";
      actBtn.addEventListener("click", function () { activateEvent(ev); });
      tdActions.appendChild(actBtn);
    }
    const editBtn = document.createElement("button");
    editBtn.type = "button";
    editBtn.className = "btn btn-small";
    editBtn.textContent = "Modifica";
    editBtn.addEventListener("click", function () { editEvent(ev); });
    tdActions.appendChild(editBtn);

    const delBtn = document.createElement("button");
    delBtn.type = "button";
    delBtn.className = "btn btn-small btn-danger";
    delBtn.textContent = "Elimina";
    delBtn.addEventListener("click", function () { deleteEvent(ev); });
    tdActions.appendChild(delBtn);

    tr.appendChild(tdState);
    tr.appendChild(tdName);
    tr.appendChild(tdDate);
    tr.appendChild(tdNote);
    tr.appendChild(tdActions);
    tbody.appendChild(tr);
  }
}

function editEvent(ev) {
  document.getElementById("event-id").value = ev.id;
  document.getElementById("e-name").value = ev.name;
  document.getElementById("e-date").value = ev.start_date || "";
  document.getElementById("e-note").value = ev.note || "";
  document.getElementById("event-form-title").textContent = "Modifica festa #" + ev.id;
}

function resetEventForm() {
  document.getElementById("event-id").value = "";
  document.getElementById("e-name").value = "";
  document.getElementById("e-date").value = "";
  document.getElementById("e-note").value = "";
  document.getElementById("event-form-title").textContent = "Nuova festa";
}

async function saveEvent(event) {
  event.preventDefault();
  const id = document.getElementById("event-id").value;
  const body = {
    name: document.getElementById("e-name").value.trim(),
    start_date: document.getElementById("e-date").value || null,
    note: document.getElementById("e-note").value.trim() || null,
  };
  if (!body.name) { showToast("Il nome festa e' obbligatorio.", true); return; }
  const url = id ? "/api/events/" + id : "/api/events";
  const method = id ? "PUT" : "POST";
  try {
    const res = await adminFetch(url, {
      method: method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) { showToast("Errore: " + (await readError(res)), true); return; }
    showToast(id ? "Festa aggiornata." : "Festa creata.", false);
    resetEventForm();
    await loadEvents();
  } catch (err) { showToast(err.message, true); }
}

async function activateEvent(ev) {
  try {
    const res = await adminFetch("/api/events/" + ev.id + "/activate", { method: "POST" });
    if (!res.ok) { showToast("Errore: " + (await readError(res)), true); return; }
    showToast('Festa "' + ev.name + '" attivata.', false);
    selectedEventId = ev.id;
    await loadEvents();
    await loadProductsAdmin();
    await loadSummary();
  } catch (err) { showToast(err.message, true); }
}

async function deleteEvent(ev) {
  if (!confirm('Eliminare la festa "' + ev.name + '" e i suoi prodotti?')) return;
  try {
    const res = await adminFetch("/api/events/" + ev.id, { method: "DELETE" });
    if (!res.ok) { showToast("Errore: " + (await readError(res)), true); return; }
    showToast("Festa eliminata.", false);
    if (selectedEventId === ev.id) selectedEventId = null;
    await loadEvents();
    await loadProductsAdmin();
  } catch (err) { showToast(err.message, true); }
}

// ---------------------------------------------------------------------------
// PRODOTTI (per festa selezionata)
// ---------------------------------------------------------------------------

let productsCache = [];

function renderProductEventSelect() {
  const sel = document.getElementById("product-event-select");
  const prev = selectedEventId;
  sel.innerHTML = "";
  for (const ev of eventsCache) {
    const opt = document.createElement("option");
    opt.value = ev.id;
    opt.textContent = ev.name + (ev.active ? " (attiva)" : "");
    sel.appendChild(opt);
  }
  if (prev !== null && eventsCache.some(function (e) { return e.id === prev; })) {
    sel.value = String(prev);
  } else if (eventsCache.length) {
    selectedEventId = eventsCache[0].id;
    sel.value = String(selectedEventId);
  }
}

async function loadProductsAdmin() {
  const tbody = document.getElementById("products-tbody");
  if (selectedEventId === null) {
    productsCache = [];
    tbody.innerHTML = '<tr><td colspan="6">Nessuna festa selezionata.</td></tr>';
    return;
  }
  try {
    const res = await fetch("/api/products?event_id=" + selectedEventId);
    if (!res.ok) throw new Error("HTTP " + res.status);
    productsCache = await res.json();
    renderProductsTable();
  } catch (err) {
    tbody.innerHTML = '<tr><td colspan="6">Errore nel caricamento prodotti.</td></tr>';
  }
}

function renderProductsTable() {
  const tbody = document.getElementById("products-tbody");
  tbody.innerHTML = "";
  if (productsCache.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6">Nessun prodotto per questa festa.</td></tr>';
    return;
  }
  for (const p of productsCache) {
    const tr = document.createElement("tr");
    const cells = [
      p.sort_order, p.name, p.category, formatEuro(p.price_cents),
      p.active ? "Si" : "No",
    ];
    for (const val of cells) {
      const td = document.createElement("td");
      td.textContent = val;
      tr.appendChild(td);
    }
    const tdActions = document.createElement("td");
    const editBtn = document.createElement("button");
    editBtn.type = "button";
    editBtn.className = "btn btn-small";
    editBtn.textContent = "Modifica";
    editBtn.addEventListener("click", function () { editProduct(p); });
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

function editProduct(p) {
  document.getElementById("product-id").value = p.id;
  document.getElementById("p-name").value = p.name;
  document.getElementById("p-category").value = p.category;
  document.getElementById("p-price").value = (p.price_cents / 100).toFixed(2);
  document.getElementById("p-sort").value = p.sort_order;
  document.getElementById("p-active").checked = p.active;
  document.getElementById("product-form-title").textContent = "Modifica prodotto #" + p.id;
}

function resetProductForm() {
  document.getElementById("product-id").value = "";
  document.getElementById("p-name").value = "";
  document.getElementById("p-category").value = "Generale";
  document.getElementById("p-price").value = "";
  document.getElementById("p-sort").value = "0";
  document.getElementById("p-active").checked = true;
  document.getElementById("product-form-title").textContent = "Nuovo prodotto";
}

async function saveProduct(event) {
  event.preventDefault();
  if (selectedEventId === null) {
    showToast("Seleziona o crea prima una festa.", true);
    return;
  }
  const id = document.getElementById("product-id").value;
  const euros = parseFloat(document.getElementById("p-price").value);
  if (isNaN(euros) || euros < 0) { showToast("Prezzo non valido.", true); return; }
  const body = {
    name: document.getElementById("p-name").value.trim(),
    category: document.getElementById("p-category").value.trim() || "Generale",
    price_cents: Math.round(euros * 100),
    active: document.getElementById("p-active").checked,
    sort_order: parseInt(document.getElementById("p-sort").value, 10) || 0,
    event_id: selectedEventId,
  };
  if (!body.name) { showToast("Il nome e' obbligatorio.", true); return; }
  const url = id ? "/api/products/" + id : "/api/products";
  const method = id ? "PUT" : "POST";
  try {
    const res = await adminFetch(url, {
      method: method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) { showToast("Errore: " + (await readError(res)), true); return; }
    showToast(id ? "Prodotto aggiornato." : "Prodotto creato.", false);
    resetProductForm();
    loadProductsAdmin();
  } catch (err) { showToast(err.message, true); }
}

async function deleteProduct(p) {
  if (!confirm('Eliminare il prodotto "' + p.name + '"?')) return;
  try {
    const res = await adminFetch("/api/products/" + p.id, { method: "DELETE" });
    if (!res.ok) { showToast("Errore: " + (await readError(res)), true); return; }
    showToast("Prodotto eliminato.", false);
    loadProductsAdmin();
  } catch (err) { showToast(err.message, true); }
}

// ---------------------------------------------------------------------------
// MAGAZZINO (scollegato dalla cassa)
// ---------------------------------------------------------------------------

let stockCache = [];

async function loadStock() {
  const tbody = document.getElementById("stock-tbody");
  try {
    const res = await fetch("/api/stock");
    if (!res.ok) throw new Error("HTTP " + res.status);
    stockCache = await res.json();
    renderStockTable();
  } catch (err) {
    tbody.innerHTML = '<tr><td colspan="6">Errore nel caricamento magazzino.</td></tr>';
  }
}

function renderStockTable() {
  const tbody = document.getElementById("stock-tbody");
  tbody.innerHTML = "";
  if (stockCache.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6">Magazzino vuoto.</td></tr>';
    return;
  }
  for (const s of stockCache) {
    const tr = document.createElement("tr");
    if (s.quantity <= 0) tr.className = "row-empty";

    const tdName = document.createElement("td");
    tdName.textContent = s.name;
    const tdCat = document.createElement("td");
    tdCat.textContent = s.category;
    const tdQty = document.createElement("td");
    tdQty.textContent = formatQty(s.quantity);
    const tdUnit = document.createElement("td");
    tdUnit.textContent = s.unit;

    // Rettifica rapida: -1 / +1
    const tdAdjust = document.createElement("td");
    const minus = document.createElement("button");
    minus.type = "button";
    minus.className = "btn btn-small";
    minus.textContent = "−1";
    minus.addEventListener("click", function () { adjustStock(s, -1); });
    const plus = document.createElement("button");
    plus.type = "button";
    plus.className = "btn btn-small";
    plus.textContent = "+1";
    plus.addEventListener("click", function () { adjustStock(s, 1); });
    tdAdjust.appendChild(minus);
    tdAdjust.appendChild(plus);

    const tdActions = document.createElement("td");
    const editBtn = document.createElement("button");
    editBtn.type = "button";
    editBtn.className = "btn btn-small";
    editBtn.textContent = "Modifica";
    editBtn.addEventListener("click", function () { editStock(s); });
    const delBtn = document.createElement("button");
    delBtn.type = "button";
    delBtn.className = "btn btn-small btn-danger";
    delBtn.textContent = "Elimina";
    delBtn.addEventListener("click", function () { deleteStock(s); });
    tdActions.appendChild(editBtn);
    tdActions.appendChild(delBtn);

    tr.appendChild(tdName);
    tr.appendChild(tdCat);
    tr.appendChild(tdQty);
    tr.appendChild(tdUnit);
    tr.appendChild(tdAdjust);
    tr.appendChild(tdActions);
    tbody.appendChild(tr);
  }
}

// Mostra la quantita' senza decimali superflui (10 invece di 10.0).
function formatQty(q) {
  return Number.isInteger(q) ? String(q) : String(q);
}

function editStock(s) {
  document.getElementById("stock-id").value = s.id;
  document.getElementById("st-name").value = s.name;
  document.getElementById("st-category").value = s.category;
  document.getElementById("st-qty").value = s.quantity;
  document.getElementById("st-unit").value = s.unit;
  document.getElementById("st-note").value = s.note || "";
  document.getElementById("stock-form-title").textContent = "Modifica articolo #" + s.id;
}

function resetStockForm() {
  document.getElementById("stock-id").value = "";
  document.getElementById("st-name").value = "";
  document.getElementById("st-category").value = "Generale";
  document.getElementById("st-qty").value = "0";
  document.getElementById("st-unit").value = "pz";
  document.getElementById("st-note").value = "";
  document.getElementById("stock-form-title").textContent = "Nuovo articolo";
}

async function saveStock(event) {
  event.preventDefault();
  const id = document.getElementById("stock-id").value;
  const body = {
    name: document.getElementById("st-name").value.trim(),
    category: document.getElementById("st-category").value.trim() || "Generale",
    unit: document.getElementById("st-unit").value.trim() || "pz",
    quantity: parseFloat(document.getElementById("st-qty").value) || 0,
    note: document.getElementById("st-note").value.trim() || null,
  };
  if (!body.name) { showToast("Il nome articolo e' obbligatorio.", true); return; }
  const url = id ? "/api/stock/" + id : "/api/stock";
  const method = id ? "PUT" : "POST";
  try {
    const res = await adminFetch(url, {
      method: method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) { showToast("Errore: " + (await readError(res)), true); return; }
    showToast(id ? "Articolo aggiornato." : "Articolo creato.", false);
    resetStockForm();
    loadStock();
  } catch (err) { showToast(err.message, true); }
}

async function adjustStock(s, delta) {
  try {
    const res = await adminFetch("/api/stock/" + s.id + "/adjust", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ delta: delta }),
    });
    if (!res.ok) { showToast("Errore: " + (await readError(res)), true); return; }
    loadStock();
  } catch (err) { showToast(err.message, true); }
}

async function deleteStock(s) {
  if (!confirm('Eliminare l\'articolo "' + s.name + '" dal magazzino?')) return;
  try {
    const res = await adminFetch("/api/stock/" + s.id, { method: "DELETE" });
    if (!res.ok) { showToast("Errore: " + (await readError(res)), true); return; }
    showToast("Articolo eliminato.", false);
    loadStock();
  } catch (err) { showToast(err.message, true); }
}

// ---------------------------------------------------------------------------
// CONFIGURAZIONE
// ---------------------------------------------------------------------------

async function loadSettings() {
  try {
    const res = await fetch("/api/settings");
    if (!res.ok) throw new Error("HTTP " + res.status);
    const s = await res.json();
    document.getElementById("s-association").value = s.association_name || "";
    document.getElementById("s-footer").value = s.footer_message || "";
    document.getElementById("s-printer").value = s.printer_mode || "dummy";
  } catch (err) {
    showToast("Impossibile caricare la configurazione.", true);
  }
}

async function saveSettings(event) {
  event.preventDefault();
  const body = {
    association_name: document.getElementById("s-association").value,
    footer_message: document.getElementById("s-footer").value,
    printer_mode: document.getElementById("s-printer").value,
  };
  const newPin = document.getElementById("s-pin").value.trim();
  if (newPin) body.admin_pin = newPin;
  try {
    const res = await adminFetch("/api/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) { showToast("Errore: " + (await readError(res)), true); return; }
    if (newPin) {
      setPin(newPin);
      document.getElementById("s-pin").value = "";
    }
    showToast("Configurazione salvata.", false);
  } catch (err) { showToast(err.message, true); }
}

// ---------------------------------------------------------------------------
// REPORT
// ---------------------------------------------------------------------------

async function loadSummary() {
  const el = document.getElementById("summary");
  try {
    const res = await fetch("/api/reports/summary");
    if (!res.ok) throw new Error("HTTP " + res.status);
    const s = await res.json();
    let html =
      "<p><strong>Ordini:</strong> " + s.orders_count + "</p>" +
      "<p><strong>Incasso totale:</strong> " + formatEuro(s.total_cents) + "</p>";
    if (s.top_products && s.top_products.length) {
      html += "<p><strong>Prodotti piu' venduti:</strong></p><ul>";
      for (const tp of s.top_products) {
        const name = tp.product_name || ("#" + (tp.product_id || "?"));
        const qty = (tp.qty != null) ? tp.qty : "";
        html += "<li>" + escapeHtml(String(name)) +
          (qty !== "" ? " — " + qty : "") + "</li>";
      }
      html += "</ul>";
    }
    el.innerHTML = html;
  } catch (err) {
    el.innerHTML = "<p>Impossibile caricare il riepilogo.</p>";
  }
}

// ---------------------------------------------------------------------------
// MANUTENZIONE
// ---------------------------------------------------------------------------

async function testPrint() {
  try {
    const res = await adminFetch("/api/printer/test", { method: "POST" });
    if (!res.ok) { showToast("Errore test stampa: " + (await readError(res)), true); return; }
    const result = await res.json();
    if (result.ok) showToast("Test stampa OK (" + result.mode + ").", false);
    else showToast("Test stampa fallito: " + (result.detail || result.mode), true);
  } catch (err) { showToast(err.message, true); }
}

async function resetData() {
  if (!confirm("ATTENZIONE: stai per azzerare gli ordini della festa attiva. Continuare?")) return;
  if (!confirm("Conferma definitiva: le vendite della festa attiva verranno azzerate (con backup). Procedere?")) return;
  try {
    const res = await adminFetch("/api/reset", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirm: true }),
    });
    if (!res.ok) { showToast("Errore reset: " + (await readError(res)), true); return; }
    showToast("Ordini festa azzerati (backup creato lato server).", false);
    loadSummary();
  } catch (err) { showToast(err.message, true); }
}

// ---------------------------------------------------------------------------
// Inizializzazione contenuto (dopo sblocco)
// ---------------------------------------------------------------------------

let contentInitialized = false;

async function initContent() {
  await loadEvents();
  loadProductsAdmin();
  loadStock();
  loadSettings();
  loadSummary();
  if (contentInitialized) return;
  contentInitialized = true;

  document.getElementById("event-form").addEventListener("submit", saveEvent);
  document.getElementById("e-reset").addEventListener("click", resetEventForm);
  document.getElementById("product-form").addEventListener("submit", saveProduct);
  document.getElementById("p-reset").addEventListener("click", resetProductForm);
  document.getElementById("product-event-select").addEventListener("change", function (e) {
    selectedEventId = parseInt(e.target.value, 10);
    resetProductForm();
    loadProductsAdmin();
  });
  document.getElementById("stock-form").addEventListener("submit", saveStock);
  document.getElementById("st-reset").addEventListener("click", resetStockForm);
  document.getElementById("settings-form").addEventListener("submit", saveSettings);
  document.getElementById("btn-refresh-summary").addEventListener("click", loadSummary);
  document.getElementById("btn-test-print").addEventListener("click", testPrint);
  document.getElementById("btn-reset").addEventListener("click", resetData);
}

// ---------------------------------------------------------------------------
// Avvio
// ---------------------------------------------------------------------------

document.getElementById("pin-submit").addEventListener("click", tryUnlock);
document.getElementById("pin-input").addEventListener("keydown", function (e) {
  if (e.key === "Enter") tryUnlock();
});

if (getPin()) {
  (async function () {
    document.getElementById("pin-input").value = getPin();
    await tryUnlock();
  })();
}
