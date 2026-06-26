// feste.js — Pagina elenco feste: crea (apre) una festa, chiudi festa,
// entra nel dettaglio per gestire prodotti e report.

"use strict";

let eventsCache = [];

async function loadEvents() {
  const tbody = document.getElementById("events-tbody");
  try {
    eventsCache = await Admin.getJSON("/api/events");
    renderEvents();
  } catch (err) {
    tbody.innerHTML = '<tr><td colspan="4">Errore nel caricamento feste.</td></tr>';
  }
}

function renderEvents() {
  const tbody = document.getElementById("events-tbody");
  tbody.innerHTML = "";
  if (eventsCache.length === 0) {
    tbody.innerHTML = '<tr><td colspan="4">Nessuna festa. Creane una con "+ Nuova festa".</td></tr>';
    return;
  }
  for (const ev of eventsCache) {
    const url = "/admin/festa/" + ev.id;
    const tr = document.createElement("tr");
    tr.className = "row-clickable" + (ev.active ? " row-active" : "");
    // Tutta la riga porta al dettaglio (accessibile da tastiera).
    tr.tabIndex = 0;
    tr.setAttribute("role", "link");
    tr.addEventListener("click", function () { window.location.href = url; });
    tr.addEventListener("keydown", function (e) {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); window.location.href = url; }
    });

    // data-label: usato dal CSS per impilare le celle come schede su telefono.
    const tdState = document.createElement("td");
    tdState.setAttribute("data-label", "Stato");
    tdState.textContent = ev.active ? "● Aperta" : "Chiusa";

    const tdName = document.createElement("td");
    tdName.setAttribute("data-label", "Nome");
    const link = document.createElement("a");
    link.href = url;
    link.className = "row-link";
    link.textContent = ev.name;
    tdName.appendChild(link);

    const tdDate = document.createElement("td");
    tdDate.setAttribute("data-label", "Data");
    tdDate.textContent = ev.start_date || "";

    const tdNote = document.createElement("td");
    tdNote.setAttribute("data-label", "Note");
    tdNote.textContent = ev.note || "";

    tr.appendChild(tdState);
    tr.appendChild(tdName);
    tr.appendChild(tdDate);
    tr.appendChild(tdNote);
    tbody.appendChild(tr);
  }
}

async function createEvent(event) {
  event.preventDefault();
  const body = {
    name: document.getElementById("e-name").value.trim(),
    start_date: document.getElementById("e-date").value || null,
    note: document.getElementById("e-note").value.trim() || null,
  };
  if (!body.name) { Admin.toast("Il nome festa e' obbligatorio.", true); return; }
  try {
    const res = await Admin.fetch("/api/events", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) { Admin.toast("Errore: " + (await Admin.readError(res)), true); return; }
    const created = await res.json();
    Admin.toast('Festa "' + created.name + '" creata e aperta.', false);
    // Entra subito nel dettaglio per impostare i prodotti.
    window.location.href = "/admin/festa/" + created.id;
  } catch (err) { Admin.toast(err.message, true); }
}

function initPage() {
  loadEvents();
  document.getElementById("btn-new-event").addEventListener("click", function () {
    document.getElementById("event-form").reset();
    Admin.openModal("event-modal");
  });
  document.getElementById("e-cancel").addEventListener("click", function () {
    Admin.closeModal("event-modal");
  });
  document.getElementById("event-form").addEventListener("submit", createEvent);
}

Admin.ready(initPage);
