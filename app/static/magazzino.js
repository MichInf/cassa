// magazzino.js — Inventario scollegato dalla cassa: CRUD via modale,
// rettifica rapida -1/+1, filtro per nome e categoria.

"use strict";

let stockCache = [];

async function loadStock() {
  const tbody = document.getElementById("stock-tbody");
  try {
    stockCache = await Admin.getJSON("/api/stock");
    populateCategoryFilter();
    renderStock();
  } catch (err) {
    tbody.innerHTML = '<tr><td colspan="6">Errore nel caricamento magazzino.</td></tr>';
  }
}

// Popola il select categorie con i valori presenti (mantenendo la scelta).
function populateCategoryFilter() {
  const sel = document.getElementById("filter-category");
  const current = sel.value;
  const cats = Array.from(new Set(stockCache.map(function (s) { return s.category; }))).sort();
  sel.innerHTML = '<option value="">Tutte le categorie</option>';
  for (const c of cats) {
    const opt = document.createElement("option");
    opt.value = c;
    opt.textContent = c;
    sel.appendChild(opt);
  }
  if (cats.indexOf(current) !== -1) sel.value = current;
}

function filteredStock() {
  const text = document.getElementById("filter-text").value.trim().toLowerCase();
  const cat = document.getElementById("filter-category").value;
  return stockCache.filter(function (s) {
    const matchText = !text || s.name.toLowerCase().indexOf(text) !== -1;
    const matchCat = !cat || s.category === cat;
    return matchText && matchCat;
  });
}

function renderStock() {
  const tbody = document.getElementById("stock-tbody");
  tbody.innerHTML = "";
  const rows = filteredStock();
  if (rows.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6">Nessun articolo.</td></tr>';
    return;
  }
  for (const s of rows) {
    const tr = document.createElement("tr");
    if (s.quantity <= 0) tr.className = "row-empty";

    // data-label: usato dal CSS per impilare le celle come schede su telefono.
    const tdName = document.createElement("td");
    tdName.setAttribute("data-label", "Articolo");
    tdName.textContent = s.name;
    const tdCat = document.createElement("td");
    tdCat.setAttribute("data-label", "Categoria");
    tdCat.textContent = s.category;
    const tdQty = document.createElement("td");
    tdQty.setAttribute("data-label", "Quantità");
    tdQty.textContent = String(s.quantity);
    const tdUnit = document.createElement("td");
    tdUnit.setAttribute("data-label", "Unità");
    tdUnit.textContent = s.unit;

    const tdAdjust = document.createElement("td");
    tdAdjust.setAttribute("data-label", "Rettifica");
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
    tdActions.setAttribute("data-label", "Azioni");
    const editBtn = document.createElement("button");
    editBtn.type = "button";
    editBtn.className = "btn btn-small";
    editBtn.textContent = "Modifica";
    editBtn.addEventListener("click", function () { openStockModal(s); });
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

function openStockModal(s) {
  document.getElementById("stock-form").reset();
  const title = document.getElementById("stock-form-title");
  if (s) {
    document.getElementById("stock-id").value = s.id;
    document.getElementById("st-name").value = s.name;
    document.getElementById("st-category").value = s.category;
    document.getElementById("st-qty").value = s.quantity;
    document.getElementById("st-unit").value = s.unit;
    document.getElementById("st-note").value = s.note || "";
    title.textContent = "Modifica articolo #" + s.id;
  } else {
    document.getElementById("stock-id").value = "";
    title.textContent = "Nuovo articolo";
  }
  Admin.openModal("stock-modal");
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
  if (!body.name) { Admin.toast("Il nome articolo e' obbligatorio.", true); return; }
  const url = id ? "/api/stock/" + id : "/api/stock";
  const method = id ? "PUT" : "POST";
  try {
    const res = await Admin.fetch(url, {
      method: method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) { Admin.toast("Errore: " + (await Admin.readError(res)), true); return; }
    Admin.toast(id ? "Articolo aggiornato." : "Articolo creato.", false);
    Admin.closeModal("stock-modal");
    loadStock();
  } catch (err) { Admin.toast(err.message, true); }
}

async function adjustStock(s, delta) {
  try {
    const res = await Admin.fetch("/api/stock/" + s.id + "/adjust", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ delta: delta }),
    });
    if (!res.ok) { Admin.toast("Errore: " + (await Admin.readError(res)), true); return; }
    loadStock();
  } catch (err) { Admin.toast(err.message, true); }
}

async function deleteStock(s) {
  if (!confirm('Eliminare l\'articolo "' + s.name + '" dal magazzino?')) return;
  try {
    const res = await Admin.fetch("/api/stock/" + s.id, { method: "DELETE" });
    if (!res.ok) { Admin.toast("Errore: " + (await Admin.readError(res)), true); return; }
    Admin.toast("Articolo eliminato.", false);
    loadStock();
  } catch (err) { Admin.toast(err.message, true); }
}

function initPage() {
  loadStock();
  document.getElementById("btn-new-stock").addEventListener("click", function () {
    openStockModal(null);
  });
  document.getElementById("st-cancel").addEventListener("click", function () {
    Admin.closeModal("stock-modal");
  });
  document.getElementById("stock-form").addEventListener("submit", saveStock);
  document.getElementById("filter-text").addEventListener("input", renderStock);
  document.getElementById("filter-category").addEventListener("change", renderStock);
}

Admin.ready(initPage);
