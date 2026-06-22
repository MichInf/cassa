// admin.js — Logica dell'area gestione (JS vanilla).
// Gestisce: sblocco con PIN, CRUD prodotti, configurazione, report e
// manutenzione (test stampa, reset). Le chiamate "admin" inviano l'header
// X-Admin-Pin; un 401 fa ricomparire la schermata di sblocco.

"use strict";

// ---------------------------------------------------------------------------
// Stato
// ---------------------------------------------------------------------------

// Chiave usata per conservare il PIN in sessionStorage (solo per la sessione).
const PIN_KEY = "festa_admin_pin";

// ---------------------------------------------------------------------------
// Utility
// ---------------------------------------------------------------------------

function formatEuro(cents) {
  return (cents / 100).toFixed(2) + " €";
}

function getPin() {
  return sessionStorage.getItem(PIN_KEY) || "";
}

function setPin(pin) {
  sessionStorage.setItem(PIN_KEY, pin);
}

function clearPin() {
  sessionStorage.removeItem(PIN_KEY);
}

function showToast(message, isError) {
  const toast = document.getElementById("toast");
  toast.textContent = message;
  toast.className = "toast show" + (isError ? " error" : "");
  clearTimeout(showToast._timer);
  showToast._timer = setTimeout(function () {
    toast.className = "toast";
  }, 3500);
}

// Estrae un messaggio di errore leggibile da una risposta.
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

// Wrapper fetch per le chiamate admin: aggiunge l'header X-Admin-Pin e
// gestisce in modo centralizzato il 401 (PIN errato/mancante).
async function adminFetch(url, options) {
  options = options || {};
  options.headers = Object.assign({}, options.headers, {
    "X-Admin-Pin": getPin(),
  });
  const res = await fetch(url, options);
  if (res.status === 401) {
    // PIN errato: torna alla schermata di sblocco.
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

// Verifica il PIN provando una chiamata admin (GET /api/settings non basta
// perche' e' pubblica; usiamo /api/printer/test? No: ha effetti. Proviamo
// invece a salvare nulla. Soluzione semplice: tentiamo una PUT settings vuota
// che il server accetta solo con PIN valido). Per evitare effetti collaterali
// usiamo una verifica leggera: una PUT /api/settings con corpo vuoto {}.
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
      // Eventuali altri errori (non 401): mostra messaggio.
      const detail = await readError(res);
      showToast("Errore: " + detail, true);
      return;
    }
    // PIN valido: mostra il contenuto e carica i dati.
    document.getElementById("pin-error").classList.add("hidden");
    document.getElementById("pin-input").value = "";
    showContent();
    initContent();
  } catch (err) {
    // adminFetch ha gia' gestito il 401 mostrando la schermata di sblocco.
  }
}

// ---------------------------------------------------------------------------
// PRODOTTI
// ---------------------------------------------------------------------------

let productsCache = [];

async function loadProductsAdmin() {
  const tbody = document.getElementById("products-tbody");
  try {
    const res = await fetch("/api/products"); // lettura pubblica
    if (!res.ok) throw new Error("HTTP " + res.status);
    productsCache = await res.json();
    productsCache.sort(function (a, b) {
      if (a.sort_order !== b.sort_order) return a.sort_order - b.sort_order;
      return a.name.localeCompare(b.name);
    });
    renderProductsTable();
  } catch (err) {
    tbody.innerHTML = '<tr><td colspan="6">Errore nel caricamento prodotti.</td></tr>';
  }
}

function renderProductsTable() {
  const tbody = document.getElementById("products-tbody");
  tbody.innerHTML = "";
  if (productsCache.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6">Nessun prodotto.</td></tr>';
    return;
  }
  for (const p of productsCache) {
    const tr = document.createElement("tr");

    const tdSort = document.createElement("td");
    tdSort.textContent = p.sort_order;

    const tdName = document.createElement("td");
    tdName.textContent = p.name;

    const tdCat = document.createElement("td");
    tdCat.textContent = p.category;

    const tdPrice = document.createElement("td");
    tdPrice.textContent = formatEuro(p.price_cents);

    const tdActive = document.createElement("td");
    tdActive.textContent = p.active ? "Si" : "No";

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

    tr.appendChild(tdSort);
    tr.appendChild(tdName);
    tr.appendChild(tdCat);
    tr.appendChild(tdPrice);
    tr.appendChild(tdActive);
    tr.appendChild(tdActions);
    tbody.appendChild(tr);
  }
}

// Riempie il form con i dati di un prodotto per modificarlo.
function editProduct(p) {
  document.getElementById("product-id").value = p.id;
  document.getElementById("p-name").value = p.name;
  document.getElementById("p-category").value = p.category;
  document.getElementById("p-price").value = (p.price_cents / 100).toFixed(2);
  document.getElementById("p-sort").value = p.sort_order;
  document.getElementById("p-active").checked = p.active;
  document.getElementById("product-form-title").textContent =
    "Modifica prodotto #" + p.id;
  window.scrollTo({ top: document.getElementById("product-form").offsetTop, behavior: "smooth" });
}

// Svuota il form prodotto (torna in modalita' "nuovo").
function resetProductForm() {
  document.getElementById("product-id").value = "";
  document.getElementById("p-name").value = "";
  document.getElementById("p-category").value = "Generale";
  document.getElementById("p-price").value = "";
  document.getElementById("p-sort").value = "0";
  document.getElementById("p-active").checked = true;
  document.getElementById("product-form-title").textContent = "Nuovo prodotto";
}

// Salva (crea o aggiorna) un prodotto.
async function saveProduct(event) {
  event.preventDefault();
  const id = document.getElementById("product-id").value;
  const euros = parseFloat(document.getElementById("p-price").value);
  if (isNaN(euros) || euros < 0) {
    showToast("Prezzo non valido.", true);
    return;
  }
  const body = {
    name: document.getElementById("p-name").value.trim(),
    category: document.getElementById("p-category").value.trim() || "Generale",
    // Converte euro -> centesimi interi, arrotondando per sicurezza.
    price_cents: Math.round(euros * 100),
    active: document.getElementById("p-active").checked,
    sort_order: parseInt(document.getElementById("p-sort").value, 10) || 0,
  };
  if (!body.name) {
    showToast("Il nome e' obbligatorio.", true);
    return;
  }

  const url = id ? "/api/products/" + id : "/api/products";
  const method = id ? "PUT" : "POST";

  try {
    const res = await adminFetch(url, {
      method: method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      showToast("Errore: " + (await readError(res)), true);
      return;
    }
    showToast(id ? "Prodotto aggiornato." : "Prodotto creato.", false);
    resetProductForm();
    loadProductsAdmin();
  } catch (err) {
    showToast(err.message, true);
  }
}

// Elimina un prodotto previa conferma.
async function deleteProduct(p) {
  if (!confirm('Eliminare il prodotto "' + p.name + '"?')) return;
  try {
    const res = await adminFetch("/api/products/" + p.id, { method: "DELETE" });
    if (!res.ok) {
      showToast("Errore: " + (await readError(res)), true);
      return;
    }
    showToast("Prodotto eliminato.", false);
    loadProductsAdmin();
  } catch (err) {
    showToast(err.message, true);
  }
}

// ---------------------------------------------------------------------------
// CONFIGURAZIONE
// ---------------------------------------------------------------------------

async function loadSettings() {
  try {
    const res = await fetch("/api/settings"); // lettura pubblica
    if (!res.ok) throw new Error("HTTP " + res.status);
    const s = await res.json();
    document.getElementById("s-association").value = s.association_name || "";
    document.getElementById("s-event").value = s.event_name || "";
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
    event_name: document.getElementById("s-event").value,
    footer_message: document.getElementById("s-footer").value,
    printer_mode: document.getElementById("s-printer").value,
  };
  // Invia admin_pin solo se l'operatore ha digitato un nuovo PIN.
  const newPin = document.getElementById("s-pin").value.trim();
  if (newPin) body.admin_pin = newPin;

  try {
    const res = await adminFetch("/api/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      showToast("Errore: " + (await readError(res)), true);
      return;
    }
    // Se e' stato cambiato il PIN, aggiorna quello in sessione.
    if (newPin) {
      setPin(newPin);
      document.getElementById("s-pin").value = "";
    }
    showToast("Configurazione salvata.", false);
  } catch (err) {
    showToast(err.message, true);
  }
}

// ---------------------------------------------------------------------------
// REPORT
// ---------------------------------------------------------------------------

async function loadSummary() {
  const el = document.getElementById("summary");
  try {
    const res = await fetch("/api/reports/summary"); // lettura pubblica
    if (!res.ok) throw new Error("HTTP " + res.status);
    const s = await res.json();
    let html =
      "<p><strong>Ordini:</strong> " + s.orders_count + "</p>" +
      "<p><strong>Incasso totale:</strong> " + formatEuro(s.total_cents) + "</p>";
    if (s.top_products && s.top_products.length) {
      html += "<p><strong>Prodotti piu' venduti:</strong></p><ul>";
      for (const tp of s.top_products) {
        // Il formato esatto di top_products dipende dal server: mostriamo
        // i campi piu' probabili in modo difensivo.
        const name = tp.product_name || tp.name || ("#" + (tp.product_id || "?"));
        const qty = (tp.quantity != null) ? tp.quantity : (tp.qty != null ? tp.qty : "");
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

// Piccola utility anti-XSS per inserire testo in innerHTML.
function escapeHtml(str) {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

// ---------------------------------------------------------------------------
// MANUTENZIONE
// ---------------------------------------------------------------------------

async function testPrint() {
  try {
    const res = await adminFetch("/api/printer/test", { method: "POST" });
    if (!res.ok) {
      showToast("Errore test stampa: " + (await readError(res)), true);
      return;
    }
    const result = await res.json();
    if (result.ok) {
      showToast("Test stampa OK (" + result.mode + ").", false);
    } else {
      showToast("Test stampa fallito: " + (result.detail || result.mode), true);
    }
  } catch (err) {
    showToast(err.message, true);
  }
}

async function resetData() {
  // Doppia conferma per evitare azzeramenti accidentali.
  if (!confirm("ATTENZIONE: stai per azzerare TUTTI gli ordini della festa. Continuare?")) {
    return;
  }
  if (!confirm("Conferma definitiva: i dati delle vendite verranno azzerati (con backup). Procedere?")) {
    return;
  }
  try {
    const res = await adminFetch("/api/reset", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirm: true }),
    });
    if (!res.ok) {
      showToast("Errore reset: " + (await readError(res)), true);
      return;
    }
    showToast("Dati festa azzerati (backup creato lato server).", false);
    loadSummary();
  } catch (err) {
    showToast(err.message, true);
  }
}

// ---------------------------------------------------------------------------
// Inizializzazione contenuto (dopo sblocco)
// ---------------------------------------------------------------------------

let contentInitialized = false;

function initContent() {
  loadProductsAdmin();
  loadSettings();
  loadSummary();
  if (contentInitialized) return;
  contentInitialized = true;

  // Listener dei form e dei pulsanti (collegati una sola volta).
  document.getElementById("product-form").addEventListener("submit", saveProduct);
  document.getElementById("p-reset").addEventListener("click", resetProductForm);
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

// Se c'e' gia' un PIN in sessione (es. ricarica pagina), prova a riusarlo.
if (getPin()) {
  tryUnlock._fromSession = true;
  // Riproviamo lo sblocco silenzioso usando il PIN salvato.
  (async function () {
    document.getElementById("pin-input").value = getPin();
    await tryUnlock();
  })();
}
