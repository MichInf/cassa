// admin-common.js — Funzionalita' condivise dalle pagine admin (JS vanilla).
// Inietta topbar+navigazione e gate PIN, gestisce l'autenticazione e fornisce
// helper (fetch con PIN, toast, modale). Ogni pagina registra la propria
// inizializzazione con Admin.ready(fn).

"use strict";

(function () {
  // Il PIN vive solo in memoria per la pagina corrente: NON viene persistito
  // (niente sessionStorage/localStorage). Cosi' ogni volta che si entra in
  // Gestione — anche tornando dalla cassa o ricaricando — il PIN e' richiesto
  // di nuovo. E' una scelta voluta per tenere l'area admin piu' protetta.
  let adminPin = "";

  // Voci di navigazione principali (Impostazioni è l'ingranaggio a sinistra,
  // la Cassa è la freccia a destra: vedi buildChrome).
  const NAV = [
    { href: "/admin/feste", label: "Feste" },
    { href: "/admin/magazzino", label: "Magazzino" },
  ];

  // Icone inline (SVG, nessuna dipendenza esterna).
  const ICON_GEAR =
    '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" ' +
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
    '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83' +
    'l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4' +
    'a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0' +
    '-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83' +
    'l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51' +
    ' 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0' +
    ' 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>';
  const ICON_ARROW_LEFT =
    '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" ' +
    'stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
    '<line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></svg>';

  const Admin = {
    _readyCb: null,
    // Registra la funzione di init della pagina (eseguita dopo lo sblocco).
    ready: function (fn) { this._readyCb = fn; },
  };
  window.Admin = Admin;

  // ----- Utility ------------------------------------------------------------

  Admin.formatEuro = function (cents) { return (cents / 100).toFixed(2) + " €"; };

  Admin.escapeHtml = function (str) {
    return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  };

  Admin.getPin = function () { return adminPin; };
  Admin.setPin = function (pin) { adminPin = pin; };
  Admin.clearPin = function () { adminPin = ""; };

  Admin.toast = function (message, isError) {
    const toast = document.getElementById("toast");
    if (!toast) return;
    toast.textContent = message;
    toast.className = "toast show" + (isError ? " error" : "");
    clearTimeout(Admin._toastTimer);
    Admin._toastTimer = setTimeout(function () { toast.className = "toast"; }, 3500);
  };

  Admin.readError = async function (res) {
    try {
      const data = await res.json();
      if (data && data.detail) {
        return typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
      }
    } catch (e) { /* corpo non JSON */ }
    return "HTTP " + res.status;
  };

  // fetch per chiamate admin: aggiunge X-Admin-Pin e gestisce il 401.
  Admin.fetch = async function (url, options) {
    options = options || {};
    options.headers = Object.assign({}, options.headers, { "X-Admin-Pin": Admin.getPin() });
    const res = await fetch(url, options);
    if (res.status === 401) {
      handleUnauthorized();
      throw new Error("PIN errato o mancante.");
    }
    return res;
  };

  // GET pubblico che ritorna JSON (o lancia).
  Admin.getJSON = async function (url) {
    const res = await fetch(url);
    if (!res.ok) throw new Error("HTTP " + res.status);
    return res.json();
  };

  // ----- Modale -------------------------------------------------------------

  Admin.openModal = function (id) {
    const el = document.getElementById(id);
    if (el) el.classList.add("modal-open");
  };
  Admin.closeModal = function (id) {
    const el = document.getElementById(id);
    if (el) el.classList.remove("modal-open");
  };

  // ----- Badge festa attiva -------------------------------------------------

  Admin.refreshBadge = async function () {
    const badge = document.getElementById("active-event-badge");
    if (!badge) return;
    try {
      const ev = await Admin.getJSON("/api/events/active");
      badge.textContent = ev && ev.name ? "Festa aperta: " + ev.name : "Nessuna festa aperta";
    } catch (e) {
      badge.textContent = "";
    }
  };

  // ----- Chrome (topbar + gate) --------------------------------------------

  function buildChrome() {
    const path = window.location.pathname;
    const links = NAV.map(function (n) {
      const active = path === n.href || (n.href === "/admin/feste" && path === "/admin");
      return '<a href="' + n.href + '" class="nav-link' + (active ? " active" : "") +
        '">' + n.label + "</a>";
    }).join("");

    const settingsActive = path === "/admin/impostazioni";

    const topbar = document.createElement("header");
    topbar.className = "topbar";
    topbar.innerHTML =
      '<div class="topbar-left">' +
        '<a href="/" class="nav-link nav-cassa" title="Torna alla cassa" ' +
          'aria-label="Torna alla cassa">' + ICON_ARROW_LEFT + "</a>" +
        '<div class="topbar-title"><h1>Gestione</h1></div>' +
      "</div>" +
      '<nav class="admin-nav">' + links +
        '<a href="/admin/impostazioni" class="nav-gear' + (settingsActive ? " active" : "") +
        '" title="Impostazioni" aria-label="Impostazioni">' + ICON_GEAR + "</a></nav>";

    const gate = document.createElement("section");
    gate.id = "pin-gate";
    gate.className = "pin-gate";
    gate.innerHTML =
      '<div class="pin-box"><h2>Area riservata</h2>' +
      "<p>Inserisci il PIN amministratore per continuare.</p>" +
      '<input id="pin-input" class="pin-input" type="password" inputmode="numeric" ' +
      'placeholder="PIN" autocomplete="off" />' +
      '<button id="pin-submit" class="btn btn-print" type="button">Entra</button>' +
      '<p id="pin-error" class="error-box hidden">PIN errato.</p></div>';

    const toast = document.createElement("div");
    toast.id = "toast";
    toast.className = "toast";
    toast.setAttribute("role", "status");

    document.body.insertBefore(topbar, document.body.firstChild);
    document.body.insertBefore(gate, topbar.nextSibling);
    document.body.appendChild(toast);

    document.getElementById("pin-submit").addEventListener("click", tryUnlock);
    document.getElementById("pin-input").addEventListener("keydown", function (e) {
      if (e.key === "Enter") tryUnlock();
    });
  }

  function showGate() {
    document.getElementById("pin-gate").classList.remove("hidden");
    const content = document.getElementById("admin-content");
    if (content) content.classList.add("hidden");
  }

  function showContent() {
    document.getElementById("pin-gate").classList.add("hidden");
    const content = document.getElementById("admin-content");
    if (content) content.classList.remove("hidden");
  }

  function handleUnauthorized() {
    Admin.clearPin();
    const errEl = document.getElementById("pin-error");
    if (errEl) {
      errEl.textContent = "PIN errato. Riprova.";
      errEl.classList.remove("hidden");
    }
    showGate();
  }

  async function tryUnlock() {
    const input = document.getElementById("pin-input");
    const pin = input.value.trim();
    if (!pin) return;
    Admin.setPin(pin);
    try {
      // PUT vuota: non modifica nulla ma richiede PIN valido.
      const res = await Admin.fetch("/api/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      if (!res.ok) {
        Admin.toast("Errore: " + (await Admin.readError(res)), true);
        return;
      }
      document.getElementById("pin-error").classList.add("hidden");
      input.value = "";
      showContent();
      Admin.refreshBadge();
      if (typeof Admin._readyCb === "function") Admin._readyCb();
    } catch (err) {
      // 401 gia' gestito da Admin.fetch.
    }
  }

  // ----- Avvio --------------------------------------------------------------

  document.addEventListener("DOMContentLoaded", function () {
    buildChrome();
    // Il PIN non e' mai memorizzato: si parte sempre dal gate, quindi ogni
    // accesso a Gestione richiede di reinserirlo.
    showGate();
    document.getElementById("pin-input").focus();
  });
})();
