# Festa Cassa

Sistema locale e leggero per gestire vendite e stampa scontrini durante le feste
dell'associazione. Gira su un Arduino UNO Q (Debian Linux) come server locale:
espone una web app per la cassa e la gestione, salva i dati in un database SQLite
e stampa gli scontrini su una stampante termica ESC/POS collegata via USB.
Funziona completamente offline, senza Internet.

## Architettura

```text
[Tablet] --Wi-Fi--> [Arduino UNO Q / Debian — 192.168.50.1]
                        |-- Access point Wi-Fi (già configurato)
                        |-- FastAPI + uvicorn (porta 8000)
                        |-- Database SQLite  (data/festa.sqlite3)
                        |-- Modulo stampa ESC/POS
                        v
                    [Stampante POS USB ESC/POS]
```

- **Backend:** Python + FastAPI servito da uvicorn.
- **Database:** SQLite (file singolo; backup = copiare un file).
- **Frontend:** HTML/CSS/JS vanilla (area cassa + area gestione).
- **Stampa:** `python-escpos` su stampante USB ESC/POS.
  In sviluppo usa il fallback `Dummy` (nessun hardware richiesto).
- **Avvio in produzione:** servizio systemd (`festa-cassa.service`).

---

## Setup sviluppo locale (Windows / Linux)

In sviluppo la stampa usa la modalità **dummy**: nessuna stampante richiesta.

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

3. Inizializza il database:

   ```bash
   python scripts/init_db.py
   ```

4. Avvia il server in modalità dummy:

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
   - Gestione: <http://127.0.0.1:8000/admin>  (PIN di default: `1234`)

---

## Deploy su Arduino UNO Q (Debian)

L'access point Wi-Fi è già configurato: SSID `FESTA-CASSA`, IP `192.168.50.1`.

### 1. Pacchetti di sistema

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-venv python3-pip sqlite3 git
```

### 2. Crea la cartella di progetto

```bash
sudo mkdir -p /opt/festa-cassa
sudo chown $USER:$USER /opt/festa-cassa
cd /opt/festa-cassa
git clone <url-repo> .
```

### 3. Virtualenv e dipendenze

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 4. Inizializza il database

```bash
python scripts/init_db.py
```

### 5. Permessi stampante USB ESC/POS (una volta sola)

VID `0x0416` / PID `0x5011` — vedi `stampante.md` per dettagli sul modello.

```bash
echo 'SUBSYSTEM=="usb", ATTRS{idVendor}=="0416", ATTRS{idProduct}=="5011", MODE="0666"' \
  | sudo tee /etc/udev/rules.d/99-escpos.rules
sudo udevadm control --reload-rules && sudo udevadm trigger
```

### 6. Installa e avvia il servizio systemd

Prima di copiare il file, sostituisci `YOUR_USER` con l'utente reale:

```bash
sed -i "s/YOUR_USER/$USER/" systemd/festa-cassa.service
sudo cp systemd/festa-cassa.service /etc/systemd/system/festa-cassa.service
sudo systemctl daemon-reload
sudo systemctl enable festa-cassa
sudo systemctl start festa-cassa
```

Verifica che sia in esecuzione:

```bash
sudo systemctl status festa-cassa
journalctl -u festa-cassa -f   # log in tempo reale
```

Il servizio si avvia automaticamente ad ogni riaccensione dell'Arduino.

---

## URL operativi durante la festa

```text
SSID Wi-Fi:   FESTA-CASSA
IP Arduino:   192.168.50.1

App / Cassa:  http://192.168.50.1:8000
Gestione:     http://192.168.50.1:8000/admin
SSH:          ssh <utente>@192.168.50.1
```

---

## Backup ed export

- **Backup del database** (consigliato prima di ogni reset):

  ```bash
  bash scripts/backup.sh
  ```

  Crea `backups/festa-YYYYMMDD-HHMMSS.sqlite3` tramite `sqlite3 .backup`.

- **Export vendite CSV:** `http://192.168.50.1:8000/api/reports/sales.csv`
  (oppure `?event_id=N` per una festa specifica).

---

## Sicurezza minima

- Cambia il **PIN admin** di default (`1234`) dalla pagina Impostazioni.
- Il sistema non deve mai essere esposto su Internet.
- Esegui un **backup prima di ogni reset** dei dati festa.

---

## Tabella API

Le rotte con PIN richiedono l'header `X-Admin-Pin`; senza/errato → 401.

### Feste

| Metodo | Endpoint                        | Descrizione                          | PIN |
| ------ | ------------------------------- | ------------------------------------ | --- |
| GET    | `/api/events`                   | Elenco feste                         | No  |
| GET    | `/api/events/active`            | Festa attiva corrente                | No  |
| POST   | `/api/events`                   | Crea e attiva una nuova festa        | Sì  |
| PUT    | `/api/events/{id}`              | Modifica nome/note/data festa        | Sì  |
| POST   | `/api/events/{id}/activate`     | Rende attiva una festa esistente     | Sì  |
| POST   | `/api/events/{id}/close`        | Chiude la festa (va nello storico)   | Sì  |
| DELETE | `/api/events/{id}`              | Elimina festa senza ordini           | Sì  |

### Prodotti

| Metodo | Endpoint                   | Descrizione           | PIN |
| ------ | -------------------------- | --------------------- | --- |
| GET    | `/api/products`            | Elenco prodotti       | No  |
| POST   | `/api/products`            | Crea prodotto         | Sì  |
| PUT    | `/api/products/{id}`       | Modifica prodotto     | Sì  |
| DELETE | `/api/products/{id}`       | Elimina prodotto      | Sì  |

### Ordini

| Metodo | Endpoint                        | Descrizione                               | PIN |
| ------ | ------------------------------- | ----------------------------------------- | --- |
| POST   | `/api/orders`                   | Crea ordine (totali calcolati server-side) | No  |
| GET    | `/api/orders`                   | Elenco ordini                             | No  |
| GET    | `/api/orders/{id}`              | Dettaglio ordine                          | No  |
| POST   | `/api/orders/{id}/print`        | Stampa / ristampa scontrino               | No  |

### Magazzino

| Metodo | Endpoint                        | Descrizione                    | PIN |
| ------ | ------------------------------- | ------------------------------ | --- |
| GET    | `/api/stock`                    | Elenco articoli magazzino      | No  |
| POST   | `/api/stock`                    | Crea articolo                  | Sì  |
| PUT    | `/api/stock/{id}`               | Modifica articolo              | Sì  |
| POST   | `/api/stock/{id}/adjust`        | Rettifica scorte (delta +/-)   | Sì  |
| DELETE | `/api/stock/{id}`               | Elimina articolo               | Sì  |

### Report

| Metodo | Endpoint                        | Descrizione                          | PIN |
| ------ | ------------------------------- | ------------------------------------ | --- |
| GET    | `/api/reports/sales.csv`        | Export vendite CSV                   | No  |
| GET    | `/api/reports/summary`          | Riepilogo vendite + top prodotti     | No  |
| GET    | `/api/reports/timeseries`       | Andamento ordini/incasso per ora     | No  |

### Sistema

| Metodo | Endpoint                   | Descrizione                          | PIN |
| ------ | -------------------------- | ------------------------------------ | --- |
| GET    | `/api/settings`            | Leggi configurazione                 | Sì  |
| PUT    | `/api/settings`            | Aggiorna configurazione              | Sì  |
| POST   | `/api/reset`               | Reset ordini festa attiva (+ backup) | Sì  |
| GET    | `/api/health`              | Stato del servizio                   | No  |
| POST   | `/api/printer/test`        | Stampa di prova                      | Sì  |

---

## File da non committare

Il database (`data/festa.sqlite3`) e la cartella `backups/` non vanno nel repo
(già in `.gitignore`): sono dati operativi generati a runtime.
