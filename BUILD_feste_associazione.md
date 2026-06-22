# BUILD.md — App feste associazione su Arduino UNO Q + stampante ESC/POS

## 1. Obiettivo
Realizzare un sistema locale e leggero per gestire vendite/scontrini durante le feste dell'associazione.

Scenario:
- Arduino UNO Q con Debian Linux come server locale.
- Database locale sul dispositivo.
- Access point Wi-Fi creato dal dispositivo.
- Tablet collegato al Wi-Fi dell'Arduino.
- Web app usata dal tablet per inserire ordini e stampare scontrini.
- Stampante POS compatibile ESC/POS collegata via USB, seriale o rete.

Il sistema deve funzionare senza Internet durante la festa.

---

## 2. Stack consigliato, leggero

### Backend
**Python + FastAPI**

Motivi:
- leggero su Linux embedded;
- facile da mantenere;
- API REST semplici;
- buona compatibilità con librerie ESC/POS;
- avvio semplice con `systemd`.

Alternative possibili:
- **Flask**: ancora più minimale, ma meno ordinato per API strutturate.
- **Node.js + Express**: valido, ma tende a portarsi dietro più dipendenze.
- **Go**: ottimo e leggerissimo in produzione, ma più lento da sviluppare.

Scelta consigliata: **FastAPI + SQLite + HTML/JS vanilla**.

### Database
**SQLite**

Motivi:
- file singolo;
- zero server DB da gestire;
- perfetto per uso locale;
- backup facile copiando un file;
- sufficiente per una festa, anche con migliaia di righe.

### Frontend
**HTML + CSS + JavaScript vanilla**

Motivi:
- niente React/Vue/Svelte se non servono;
- caricamento veloce su tablet;
- manutenzione semplice;
- si può rendere installabile come PWA in un secondo momento.

### Stampa
Stampante termica compatibile **ESC/POS**.

Connessioni supportate, in ordine di preferenza:
1. **Ethernet/Wi-Fi TCP 9100**: più stabile se la stampante è di rete.
2. **USB**: buona, ma richiede gestione permessi Linux/udev.
3. **Seriale / USB-seriale**: semplice, ma attenzione a baud rate e porta `/dev/ttyUSB0`.

Libreria consigliata:
- `python-escpos` oppure `escpos-thermal`.

---

## 3. Architettura

```text
[Tablet]
   |
   | Wi-Fi locale creato da Arduino UNO Q
   v
[Arduino UNO Q - Debian Linux]
   |-- FastAPI web server
   |-- SQLite database
   |-- modulo stampa ESC/POS
   |-- Access point Wi-Fi configurato tramite script
   |
   v
[Stampante POS ESC/POS]
```

Indirizzo consigliato del server:

```text
http://192.168.50.1:8000
```

SSID consigliato:

```text
FESTA-CASSA
```

---

## 4. Funzioni minime versione 1

### Area cassa
- Lista prodotti divisi per categoria.
- Carrello ordine.
- Quantità + / -.
- Totale ordine.
- Pulsante `Stampa scontrino`.
- Pulsante `Annulla ordine`.

### Area gestione
- Inserimento/modifica prodotti.
- Prezzo prodotto.
- Categoria prodotto.
- Prodotto attivo/non attivo.
- Esportazione vendite CSV.
- Reset dati festa, protetto da conferma.

### Stampa scontrino
Lo scontrino deve contenere:
- nome associazione;
- nome festa/evento;
- data e ora;
- numero progressivo ordine;
- righe prodotto: quantità, nome, totale riga;
- totale complessivo;
- eventuale messaggio finale;
- taglio carta.

---

## 5. Struttura progetto

```text
festa-cassa/
  app/
    main.py
    db.py
    models.py
    printer.py
    settings.py
    static/
      index.html
      app.js
      style.css
  data/
    festa.sqlite3
  scripts/
    init_db.py
    backup.sh
    setup_ap.sh
    disable_ap.sh
  systemd/
    festa-cassa.service
  requirements.txt
  README.md
  BUILD.md
```

---

## 6. Schema database SQLite

### Tabella `products`

```sql
CREATE TABLE IF NOT EXISTS products (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  category TEXT NOT NULL DEFAULT 'Generale',
  price_cents INTEGER NOT NULL,
  active INTEGER NOT NULL DEFAULT 1,
  sort_order INTEGER NOT NULL DEFAULT 0
);
```

### Tabella `orders`

```sql
CREATE TABLE IF NOT EXISTS orders (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT NOT NULL,
  total_cents INTEGER NOT NULL,
  printed INTEGER NOT NULL DEFAULT 0,
  note TEXT
);
```

### Tabella `order_items`

```sql
CREATE TABLE IF NOT EXISTS order_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  order_id INTEGER NOT NULL,
  product_id INTEGER,
  product_name TEXT NOT NULL,
  quantity INTEGER NOT NULL,
  unit_price_cents INTEGER NOT NULL,
  line_total_cents INTEGER NOT NULL,
  FOREIGN KEY(order_id) REFERENCES orders(id)
);
```

### Tabella `settings`

```sql
CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
```

---

## 7. API previste

### Prodotti

```text
GET    /api/products
POST   /api/products
PUT    /api/products/{id}
DELETE /api/products/{id}
```

### Ordini

```text
POST   /api/orders
GET    /api/orders/{id}
GET    /api/orders
POST   /api/orders/{id}/print
```

### Report

```text
GET /api/reports/sales.csv
GET /api/reports/summary
```

### Sistema

```text
GET  /api/health
POST /api/printer/test
```

---

## 8. Setup base sistema Linux

Aggiornare il sistema:

```bash
sudo apt update
sudo apt upgrade -y
```

Installare pacchetti base:

```bash
sudo apt install -y python3 python3-venv python3-pip sqlite3 git hostapd dnsmasq
```

Creare cartella progetto:

```bash
sudo mkdir -p /opt/festa-cassa
sudo chown $USER:$USER /opt/festa-cassa
cd /opt/festa-cassa
```

Creare virtualenv:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

`requirements.txt`:

```text
fastapi
uvicorn[standard]
python-escpos
pydantic
```

Installazione:

```bash
pip install -r requirements.txt
```

---

## 9. Access point Wi-Fi

La configurazione dell'access point non viene mantenuta dentro questo documento.

Per configurare subito l'Arduino UNO Q come access point usare lo script:

```bash
sudo bash scripts/setup_ap.sh
```

Impostazioni operative consigliate:

```text
SSID: FESTA-CASSA
IP Arduino/AP: 192.168.50.1
URL app: http://192.168.50.1:8000
Admin: http://192.168.50.1:8000/admin
Cassa: http://192.168.50.1:8000/cassa
SSH: ssh <utente>@192.168.50.1
```

La password Wi-Fi viene chiesta dallo script durante l'esecuzione e non deve essere salvata nel repository.

Per disabilitare l'access point, usare:

```bash
sudo bash scripts/disable_ap.sh
```

Attenzione: se si lancia lo script mentre si è collegati via SSH sulla stessa interfaccia Wi-Fi che verrà trasformata in access point, la connessione potrebbe cadere. Preferire accesso via USB/seriale, Ethernet o console locale durante la prima configurazione.

---

## 10. Servizio systemd

### `systemd/festa-cassa.service`

```ini
[Unit]
Description=Festa Cassa Web Server
After=network-online.target
Wants=network-online.target

[Service]
WorkingDirectory=/opt/festa-cassa
ExecStart=/opt/festa-cassa/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=3
User=YOUR_USER
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

Installazione servizio:

```bash
sudo cp systemd/festa-cassa.service /etc/systemd/system/festa-cassa.service
sudo systemctl daemon-reload
sudo systemctl enable festa-cassa
sudo systemctl start festa-cassa
```

Log:

```bash
journalctl -u festa-cassa -f
```

---

## 11. Modulo stampa ESC/POS

### Stampante di rete TCP 9100

```python
from escpos.printer import Network

p = Network("192.168.50.10", port=9100)
p.set(align="center", bold=True, width=2, height=2)
p.text("FESTA ASSOCIAZIONE\n")
p.set(align="left", bold=False, width=1, height=1)
p.text("Ordine #1\n")
p.text("2 x Panino       10.00 EUR\n")
p.text("--------------------------\n")
p.text("Totale:          10.00 EUR\n")
p.cut()
```

### Stampante USB

Individuare vendor/product:

```bash
lsusb
```

Esempio:

```python
from escpos.printer import Usb

p = Usb(0x04b8, 0x0202)
p.text("Test stampa\n")
p.cut()
```

### Stampante seriale

```python
from escpos.printer import Serial

p = Serial(devfile="/dev/ttyUSB0", baudrate=9600)
p.text("Test stampa\n")
p.cut()
```

---

## 12. Backup dati

Backup manuale:

```bash
mkdir -p backups
sqlite3 data/festa.sqlite3 ".backup backups/festa-$(date +%Y%m%d-%H%M%S).sqlite3"
```

Esportazione vendite CSV:

```sql
SELECT
  orders.id,
  orders.created_at,
  order_items.product_name,
  order_items.quantity,
  order_items.unit_price_cents,
  order_items.line_total_cents
FROM order_items
JOIN orders ON orders.id = order_items.order_id
ORDER BY orders.id ASC;
```

---

## 13. Sicurezza minima

- Password Wi-Fi non banale.
- Area gestione protetta da PIN o password.
- Nessuna esposizione su Internet.
- Backup prima di ogni reset festa.
- Disabilitare servizi non necessari.
- Stampante e tablet nella stessa rete locale.

---

## 14. Scelte da confermare prima dello sviluppo

1. Modello stampante e tipo collegamento: USB, seriale o rete.
2. Numero tablet/casse contemporanee.
3. Serve gestione magazzino o solo vendita?
4. Serve differenziare cucina/bar/cassa?
5. Serve doppia stampa: cliente + cucina?
6. Serve pagamento contanti/carta o solo totale?
7. Serve login operatori?

---

## 15. Roadmap sviluppo

### Fase 1 — MVP locale
- Server FastAPI.
- SQLite.
- Interfaccia tablet.
- Creazione ordine.
- Stampa scontrino.
- Prodotti configurabili da file o DB.

### Fase 2 — Gestione evento
- Pannello prodotti.
- Report vendite.
- Export CSV.
- Backup DB.

### Fase 3 — Robustezza festa
- Ristampa ultimo scontrino.
- Coda stampa in caso di errore.
- Stato stampante.
- PWA offline cache.
- Schermata diagnostica.

---

## 16. Raccomandazione finale

Per non appesantire l'infrastruttura:

```text
FastAPI + SQLite + HTML/CSS/JS vanilla + python-escpos + systemd
```

Evitare inizialmente:
- Docker;
- PostgreSQL/MySQL;
- React o framework frontend pesanti;
- code broker tipo Redis/RabbitMQ;
- autenticazioni complesse;
- cloud obbligatorio.

Questa architettura è semplice, locale, ripristinabile e adatta a una festa dove la priorità è vendere e stampare senza perdere tempo.
