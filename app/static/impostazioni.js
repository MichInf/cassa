// impostazioni.js — Configurazione scontrino (associazione, footer, stampante, PIN).

"use strict";

async function loadSettings() {
  try {
    const s = await Admin.getJSON("/api/settings");
    document.getElementById("s-association").value = s.association_name || "";
    document.getElementById("s-footer").value = s.footer_message || "";
    document.getElementById("s-printer").value = s.printer_mode || "dummy";
  } catch (err) {
    Admin.toast("Impossibile caricare le impostazioni.", true);
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
    const res = await Admin.fetch("/api/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) { Admin.toast("Errore: " + (await Admin.readError(res)), true); return; }
    if (newPin) {
      Admin.setPin(newPin);
      document.getElementById("s-pin").value = "";
    }
    Admin.toast("Impostazioni salvate.", false);
  } catch (err) { Admin.toast(err.message, true); }
}

// --- Manutenzione (test stampa + reset ordini festa aperta) -----------------

async function testPrint() {
  try {
    const res = await Admin.fetch("/api/printer/test", { method: "POST" });
    if (!res.ok) { Admin.toast("Errore test stampa: " + (await Admin.readError(res)), true); return; }
    const result = await res.json();
    if (result.ok) Admin.toast("Test stampa OK (" + result.mode + ").", false);
    else Admin.toast("Test stampa fallito: " + (result.detail || result.mode), true);
  } catch (err) { Admin.toast(err.message, true); }
}

async function resetData() {
  if (!confirm("ATTENZIONE: stai per azzerare gli ordini della festa aperta. Continuare?")) return;
  if (!confirm("Conferma definitiva: le vendite della festa aperta verranno azzerate (con backup). Procedere?")) return;
  try {
    const res = await Admin.fetch("/api/reset", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirm: true }),
    });
    if (!res.ok) { Admin.toast("Errore reset: " + (await Admin.readError(res)), true); return; }
    Admin.toast("Ordini festa azzerati (backup creato lato server).", false);
  } catch (err) { Admin.toast(err.message, true); }
}

function initPage() {
  loadSettings();
  document.getElementById("settings-form").addEventListener("submit", saveSettings);
  document.getElementById("btn-test-print").addEventListener("click", testPrint);
  document.getElementById("btn-reset").addEventListener("click", resetData);
}

Admin.ready(initPage);
