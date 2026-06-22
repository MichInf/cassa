# Festa Cassa

Sistema locale e leggero per gestire vendite e stampa scontrini durante le feste
dell'associazione. Gira su un Arduino UNO Q (Debian Linux) come server locale:
crea un access point Wi-Fi a cui si collegano i tablet, espone una web app per la
cassa e la gestione, salva i dati in un database SQLite e stampa gli scontrini su
una stampante termica ESC/POS collegata via USB. Funziona completamente offline,
senza Internet, durante la festa.

## Stack e architettura

```text
[Tablet] --Wi-Fi--> [Arduino UNO Q / Debian]
                        |-- Access point Wi-Fi (hostapd + dnsmasq)
                        |-- FastAPI web server (uvicorn)
                        |-- Database SQLite (data/festa.sqlite3)
                        |-- Modulo stampa ESC/POS
                        v
                    [Stampante POS USB ESC/POS]
```

- **Backend:** Python + FastAPI servito da uvicorn.
- **Database:** SQLite (file singolo, backup copiando un file).
- **Frontend:** HTML/CSS/JS vanilla (area cassa + area gestione).
- **Stampa:** `python-escpos` su stampante USB ESC/POS. In sviluppo usa il
  fallback `Dummy` (nessun hardware richiesto).
- **Avvio in produzione:** servizio `systemd`.

## Requisiti

- Python 3 (con `venv` e `pip`).
- `sqlite3` (per backup e ispezione DB).
- In produzione (Arduino UNO Q / Debian): `hostapd`, `dnsmasq`, `git`,
  stampante USB ESC/POS (VID `0x0416`, PID `0x5011`).

## Setup sviluppo locale (Windows / Linux)

In sviluppo la stampa usa la modalità **dummy**: nessuna stampante necessaria.

1. Crea e attiva il virtualenv:

   ```bash
   # Linux / macOS
   python3 -m venv .venv
   source .venv/bin/activate
   ```

   ```powershell
   # Windows (PowerShell)
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   ```

2. Installa le dipendenze:

   ```bash
   pip install -r requirements.txt
   ```

3. Inizializza il database (schema + prodotti demo):

   ```bash
   python scripts/init_db.py
   ```

4. Imposta la modalità stampa dummy e avvia il server:

   ```bash
   # Linux / macOS
   export FESTA_PRINTER_MODE=dummy
   uvicorn app.main:app --reload
   ```

   ```powershell
   # Windows (PowerShell)
   $env:FESTA_PRINTER_MODE = "dummy"
   uvicorn app.main:app --reload
   ```

5. Apri il browser:
   - Cassa: <http://127.0.0.1:8000>
   - Gestione: <http://127.0.0.1:8000/admin> (PIN admin di default: `1234`)

## Deploy su Arduino UNO Q (Debian)

1. **Aggiorna il sistema e installa i pacchetti base** (sezione 8 del BUILD):

   ```bash
   sudo apt update
   sudo apt upgrade -y
   sudo apt install -y python3 python3-venv python3-pip sqlite3 git hostapd dnsmasq
   ```

2. **Crea la cartella di progetto** e copiaci dentro il codice:

   ```bash
   sudo mkdir -p /opt/festa-cassa
   sudo chown $USER:$USER /opt/festa-cassa
   cd /opt/festa-cassa
   # copia/clona qui i file del progetto
   ```

3. **Virtualenv e dipendenze:**

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

4. **Inizializza il database:**

   ```bash
   python scripts/init_db.py
   ```

5. **Configura la stampante USB ESC/POS** (vedi `stampante.md`,
   VID `0x0416` PID `0x5011`). Regola udev per i permessi (una volta sola):

   ```bash
   echo 'SUBSYSTEM=="usb", ATTRS{idVendor}=="0416", ATTRS{idProduct}=="5011", MODE="0666"' \
     | sudo tee /etc/udev/rules.d/99-escpos.rules
   sudo udevadm control --reload-rules && sudo udevadm trigger
   ```

   In produzione la stampa usa la modalità **usb** (impostata dal service
   systemd tramite `FESTA_PRINTER_MODE=usb`).

6. **Installa il servizio systemd** (sezione 10 del BUILD). Modifica prima
   `User=YOUR_USER` nel file con l'utente reale:

   ```bash
   sudo cp systemd/festa-cassa.service /etc/systemd/system/festa-cassa.service
   sudo systemctl daemon-reload
   sudo systemctl enable festa-cassa
   sudo systemctl start festa-cassa
   journalctl -u festa-cassa -f   # log in tempo reale
   ```

7. **Configura l'access point Wi-Fi:**

   ```bash
   sudo bash scripts/setup_ap.sh
   ```

   Per disabilitarlo e tornare alla rete normale:

   ```bash
   sudo bash scripts/disable_ap.sh
   ```

## URL operativi durante la festa

(Sezione 9 del BUILD)

```text
SSID Wi-Fi:   FESTA-CASSA
IP Arduino:   192.168.50.1
App / Cassa:  http://192.168.50.1:8000
Gestione:     http://192.168.50.1:8000/admin
SSH:          ssh <utente>@192.168.50.1
```

La password Wi-Fi viene chiesta da `scripts/setup_ap.sh` durante l'esecuzione e
non va salvata nel repository.

## Backup ed export

- **Backup del database** (consigliato prima di ogni reset festa):

  ```bash
  bash scripts/backup.sh
  ```

  Crea `backups/festa-YYYYMMDD-HHMMSS.sqlite3` tramite `sqlite3 .backup`.

- **Export vendite in CSV:** scarica da
  <http://192.168.50.1:8000/api/reports/sales.csv> (oppure
  <http://127.0.0.1:8000/api/reports/sales.csv> in locale).

## Sicurezza minima

(Sezione 13 del BUILD)

- Cambia il **PIN admin** di default (`1234`) dalla pagina di gestione.
- Usa una **password Wi-Fi** non banale per l'access point.
- **Nessuna esposizione su Internet:** il sistema deve restare sulla rete
  locale della festa.
- Esegui un **backup prima di ogni reset** dei dati festa.
- Tieni stampante e tablet sulla stessa rete locale.

## Tabella sintetica delle API

| Metodo | Endpoint                     | Descrizione                              | PIN |
| ------ | ---------------------------- | ---------------------------------------- | --- |
| GET    | `/api/products`              | Elenco prodotti                          | No  |
| POST   | `/api/products`              | Crea prodotto                            | Sì  |
| PUT    | `/api/products/{id}`         | Modifica prodotto                        | Sì  |
| DELETE | `/api/products/{id}`         | Elimina prodotto                         | Sì  |
| POST   | `/api/orders`               | Crea ordine (totali calcolati lato server) | No  |
| GET    | `/api/orders`               | Elenco ordini                            | No  |
| GET    | `/api/orders/{id}`          | Dettaglio ordine                         | No  |
| POST   | `/api/orders/{id}/print`    | Stampa/ristampa scontrino                | No  |
| GET    | `/api/reports/sales.csv`    | Export vendite CSV                       | No  |
| GET    | `/api/reports/summary`      | Riepilogo vendite                        | No  |
| GET    | `/api/settings`             | Leggi configurazione                     | Sì  |
| PUT    | `/api/settings`             | Aggiorna configurazione                  | Sì  |
| POST   | `/api/reset`                | Reset dati festa (con conferma)          | Sì  |
| GET    | `/api/health`               | Stato del servizio                       | No  |
| POST   | `/api/printer/test`         | Stampa di prova                          | Sì  |

Le rotte con PIN richiedono l'header `X-Admin-Pin`; senza/errato rispondono 401.

## Nota su file da non committare

Il database (`data/festa.sqlite3`), i suoi file temporanei e la cartella
`backups/` **non vanno committati** (vedi `.gitignore`). Sono dati operativi
locali, generati a runtime.
