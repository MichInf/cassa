#!/usr/bin/env bash
#
# disable_ap.sh — Disabilita l'access point Wi-Fi e ripristina la rete normale.
#
# Operazione speculare a scripts/setup_ap.sh: ferma e disabilita hostapd e
# dnsmasq, rimuove l'IP statico assegnato all'interfaccia Wi-Fi e riconsegna
# la gestione della rete a NetworkManager (con fallback a wpa_supplicant).
#
# Caratteristiche:
#   - richiede privilegi di root;
#   - stampa ogni operazione che esegue;
#   - idempotente: non fallisce se un servizio e' gia' fermo/disabilitato.
#
# Uso:
#   sudo bash scripts/disable_ap.sh
#
# NOTA: se sei collegato via SSH attraverso questa stessa interfaccia Wi-Fi,
# la connessione potrebbe cadere. Preferisci console locale, USB/seriale o
# Ethernet durante questa operazione.

set -euo pipefail

# Interfaccia Wi-Fi usata per l'access point (coerente con setup_ap.sh).
WLAN_IFACE="${WLAN_IFACE:-wlan0}"
# IP statico assegnato all'interfaccia in modalita' AP (da rimuovere).
AP_IP="${AP_IP:-192.168.50.1}"

# --- Verifica privilegi root ---
if [[ "${EUID}" -ne 0 ]]; then
  echo "ERRORE: questo script deve essere eseguito come root." >&2
  echo "        Riprova con: sudo bash scripts/disable_ap.sh" >&2
  exit 1
fi

echo "== Disabilitazione access point Wi-Fi (interfaccia: ${WLAN_IFACE}) =="

# Ferma e disabilita un servizio in modo idempotente.
# Non fallisce se il servizio non esiste o e' gia' fermo/disabilitato.
stop_and_disable() {
  local svc="$1"

  if ! systemctl list-unit-files "${svc}.service" >/dev/null 2>&1; then
    echo "  - ${svc}: unit non presente, salto."
    return 0
  fi

  if systemctl is-active --quiet "${svc}"; then
    echo "  - ${svc}: fermo il servizio..."
    systemctl stop "${svc}" || echo "    (avviso: impossibile fermare ${svc}, proseguo)"
  else
    echo "  - ${svc}: gia' fermo."
  fi

  if systemctl is-enabled --quiet "${svc}" 2>/dev/null; then
    echo "  - ${svc}: disabilito l'avvio automatico..."
    systemctl disable "${svc}" || echo "    (avviso: impossibile disabilitare ${svc}, proseguo)"
  else
    echo "  - ${svc}: gia' disabilitato."
  fi
}

# 1) Ferma e disabilita i servizi dell'access point.
stop_and_disable hostapd
stop_and_disable dnsmasq

# 2) Rimuove l'IP statico dell'AP dall'interfaccia Wi-Fi (idempotente).
if command -v ip >/dev/null 2>&1; then
  if ip addr show dev "${WLAN_IFACE}" 2>/dev/null | grep -q "${AP_IP}"; then
    echo "  - rimuovo l'IP statico ${AP_IP} da ${WLAN_IFACE}..."
    ip addr del "${AP_IP}/24" dev "${WLAN_IFACE}" 2>/dev/null \
      || echo "    (avviso: IP gia' assente su ${WLAN_IFACE})"
  else
    echo "  - nessun IP statico ${AP_IP} su ${WLAN_IFACE}, salto."
  fi

  # Riporta l'interfaccia in stato pulito.
  echo "  - reset dell'interfaccia ${WLAN_IFACE}..."
  ip link set "${WLAN_IFACE}" down 2>/dev/null || true
  ip addr flush dev "${WLAN_IFACE}" 2>/dev/null || true
  ip link set "${WLAN_IFACE}" up 2>/dev/null || true
else
  echo "  - comando 'ip' non disponibile, salto la pulizia dell'indirizzo."
fi

# 3) Ripristina la gestione di rete normale.
#    Preferito: NetworkManager. Fallback: wpa_supplicant + dhcpcd.
echo "== Ripristino gestione di rete normale =="

if systemctl list-unit-files NetworkManager.service >/dev/null 2>&1; then
  echo "  - riavvio NetworkManager..."
  systemctl unmask NetworkManager 2>/dev/null || true
  systemctl enable NetworkManager 2>/dev/null || true
  systemctl restart NetworkManager \
    || echo "    (avviso: impossibile riavviare NetworkManager)"
else
  echo "  - NetworkManager non presente, uso wpa_supplicant/dhcpcd come fallback."

  if systemctl list-unit-files "wpa_supplicant.service" >/dev/null 2>&1; then
    echo "  - riavvio wpa_supplicant..."
    systemctl unmask wpa_supplicant 2>/dev/null || true
    systemctl enable wpa_supplicant 2>/dev/null || true
    systemctl restart wpa_supplicant \
      || echo "    (avviso: impossibile riavviare wpa_supplicant)"
  fi

  if systemctl list-unit-files "dhcpcd.service" >/dev/null 2>&1; then
    echo "  - riavvio dhcpcd..."
    systemctl restart dhcpcd \
      || echo "    (avviso: impossibile riavviare dhcpcd)"
  fi
fi

echo "OK: access point disabilitato e gestione di rete ripristinata."
echo "    Se necessario, riconnetti la Wi-Fi alla rete desiderata."
