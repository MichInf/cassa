#!/usr/bin/env bash
set -euo pipefail

if [ "${EUID}" -ne 0 ]; then
  echo "Esegui con sudo: sudo bash scripts/setup_ap.sh"
  exit 1
fi

DEFAULT_SSID="ECACASSA-AP"
DEFAULT_IP="100.100.100.1"
DEFAULT_DHCP_START="100.100.100.20"
DEFAULT_DHCP_END="100.100.100.100"
DEFAULT_CHANNEL="6"

WIFI_IFACE="${WIFI_IFACE:-}"
if [ -z "${WIFI_IFACE}" ]; then
  if command -v iw >/dev/null 2>&1; then
    WIFI_IFACE="$(iw dev | awk '$1=="Interface" {print $2; exit}')"
  fi
fi
if [ -z "${WIFI_IFACE}" ]; then
  WIFI_IFACE="wlan0"
fi

read -r -p "Interfaccia Wi-Fi [${WIFI_IFACE}]: " INPUT_IFACE
WIFI_IFACE="${INPUT_IFACE:-$WIFI_IFACE}"

read -r -p "SSID access point [${DEFAULT_SSID}]: " INPUT_SSID
SSID="${INPUT_SSID:-$DEFAULT_SSID}"

while true; do
  read -r -s -p "Password Wi-Fi WPA2, minimo 8 caratteri: " WIFI_PASSWORD
  echo
  if [ "${#WIFI_PASSWORD}" -ge 8 ]; then
    break
  fi
  echo "Password troppo corta. Deve avere almeno 8 caratteri."
done

AP_IP="${AP_IP:-$DEFAULT_IP}"
DHCP_START="${DHCP_START:-$DEFAULT_DHCP_START}"
DHCP_END="${DHCP_END:-$DEFAULT_DHCP_END}"
CHANNEL="${CHANNEL:-$DEFAULT_CHANNEL}"

cat <<MSG

Configuro AP:
- interfaccia: ${WIFI_IFACE}
- SSID: ${SSID}
- IP server: ${AP_IP}
- DHCP: ${DHCP_START} - ${DHCP_END}

ATTENZIONE: se sei collegato via SSH usando questa stessa interfaccia Wi-Fi, potresti perdere la connessione.
MSG
read -r -p "Continuare? [scrivi SI]: " CONFIRM
if [ "${CONFIRM}" != "SI" ]; then
  echo "Annullato."
  exit 1
fi

apt update
apt install -y hostapd dnsmasq iw iproute2

systemctl stop hostapd 2>/dev/null || true
systemctl stop dnsmasq 2>/dev/null || true

if systemctl list-unit-files NetworkManager.service >/dev/null 2>&1; then
  mkdir -p /etc/NetworkManager/conf.d
  cat > /etc/NetworkManager/conf.d/festa-cassa-ap-unmanaged.conf <<NMEOF
[keyfile]
unmanaged-devices=interface-name:${WIFI_IFACE}
NMEOF
  systemctl restart NetworkManager || true
fi

cat > /etc/hostapd/hostapd.conf <<HOSTAPDEOF
interface=${WIFI_IFACE}
driver=nl80211
ssid=${SSID}
hw_mode=g
channel=${CHANNEL}
wmm_enabled=0
auth_algs=1
wpa=2
wpa_passphrase=${WIFI_PASSWORD}
wpa_key_mgmt=WPA-PSK
rsn_pairwise=CCMP
HOSTAPDEOF
chmod 600 /etc/hostapd/hostapd.conf

if [ -f /etc/default/hostapd ]; then
  sed -i 's|^#*DAEMON_CONF=.*|DAEMON_CONF="/etc/hostapd/hostapd.conf"|' /etc/default/hostapd
fi

cat > /etc/dnsmasq.d/festa-cassa.conf <<DNSMASQEOF
interface=${WIFI_IFACE}
bind-interfaces
dhcp-range=${DHCP_START},${DHCP_END},255.255.255.0,24h
address=/cassa.local/${AP_IP}
DNSMASQEOF

cat > /etc/systemd/system/festa-cassa-ap-net.service <<SERVICEEOF
[Unit]
Description=Festa Cassa AP static network
Before=hostapd.service dnsmasq.service
After=sys-subsystem-net-devices-${WIFI_IFACE}.device
Wants=sys-subsystem-net-devices-${WIFI_IFACE}.device

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/bash -c '/usr/sbin/ip link set ${WIFI_IFACE} up && /usr/sbin/ip addr flush dev ${WIFI_IFACE} && /usr/sbin/ip addr add ${AP_IP}/24 dev ${WIFI_IFACE}'
ExecStop=/bin/bash -c '/usr/sbin/ip addr flush dev ${WIFI_IFACE}'

[Install]
WantedBy=multi-user.target
SERVICEEOF

systemctl unmask hostapd || true
systemctl daemon-reload
systemctl enable festa-cassa-ap-net hostapd dnsmasq
systemctl restart festa-cassa-ap-net
systemctl restart dnsmasq
systemctl restart hostapd

cat <<DONE

Access point configurato.

Collegati alla rete Wi-Fi:
SSID: ${SSID}
Password: quella appena inserita

Indirizzi utili:
- App:   http://${AP_IP}:8000
- Admin: http://${AP_IP}:8000/admin
- Cassa: http://${AP_IP}:8000/cassa
- SSH:   ssh <utente>@${AP_IP}

Verifica stato servizi:
systemctl status hostapd dnsmasq festa-cassa-ap-net
DONE
