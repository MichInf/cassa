# Festa Cassa — Design (MVP v1)

Data: 2026-06-22

## Obiettivo
Sistema locale e leggero per gestire vendite e scontrini durante le feste
dell'associazione. Gira su Arduino UNO Q (Debian) come server locale, tablet
collegati via Wi-Fi access point, stampante termica ESC/POS via USB. Nessun
Internet richiesto durante la festa.

Riferimento completo: `BUILD_feste_associazione.md`.

## Decisioni confermate (sezione 14 del BUILD)
1. Stampante: **USB ESC/POS**, VID `0x0416` PID `0x5011` (vedi `stampante.md`).
2. Ambito: **MVP v1 completo** (cassa + gestione + report/CSV + backup + stampa).
3. Pagamento: **solo totale** (nessun campo metodo pagamento).
4. Admin: **protetto da PIN** semplice configurabile.
5. Stampa: **solo scontrino cliente** (nessuna comanda cucina, nessuna doppia stampa).
6. Magazzino: no, solo vendita.
7. Login operatori: no.

## Stack
FastAPI + SQLite + HTML/CSS/JS vanilla + python-escpos + systemd. Niente Docker,
niente DB server, niente framework frontend. Sviluppo cross-platform: su
Windows/dev la stampa usa un fallback `Dummy` di python-escpos così l'app è
testabile ovunque; in produzione su Linux usa la stampante USB reale.

## Struttura progetto
```
app/
  main.py        # FastAPI app: API REST + serve frontend statico
  db.py          # connessione SQLite + schema + helper accesso dati
  models.py      # modelli Pydantic request/response
  printer.py     # modulo stampa ESC/POS (USB reale o Dummy)
  settings.py    # lettura/scrittura tabella settings + verifica PIN
  static/
    index.html   # area cassa
    admin.html   # area gestione
    app.js        # logica cassa
    admin.js      # logica gestione
    style.css
data/
  festa.sqlite3  # creato a runtime (non in git)
scripts/
  init_db.py     # crea schema + prodotti demo
  backup.sh
  setup_ap.sh    # già presente
  disable_ap.sh
systemd/
  festa-cassa.service
requirements.txt
README.md
tests/           # pytest
```

## Schema DB
Identico alla sezione 6 del BUILD: tabelle `products`, `orders`, `order_items`,
`settings`. Tutti gli importi in centesimi interi (`*_cents`). Nessun campo
metodo pagamento.

`settings` chiavi note:
- `association_name`
- `event_name`
- `footer_message`
- `admin_pin`
- `printer_mode` (`usb` | `dummy`) — default `dummy` in dev

## Componenti (interfacce)

### db.py
- `DB_PATH` configurabile via env `FESTA_DB_PATH` (default `data/festa.sqlite3`).
- `get_connection()` → sqlite3.Connection con `row_factory = sqlite3.Row` e
  `PRAGMA foreign_keys = ON`.
- `init_schema(conn)` — crea le tabelle se mancanti.
- `seed_defaults(conn)` — inserisce settings di default e prodotti demo se vuoto.

### models.py (Pydantic)
- `ProductIn` { name, category, price_cents, active, sort_order }
- `ProductOut` = ProductIn + { id }
- `OrderItemIn` { product_id, quantity }
- `OrderIn` { items: list[OrderItemIn], note: str | None }
- `OrderItemOut` { product_id, product_name, quantity, unit_price_cents, line_total_cents }
- `OrderOut` { id, created_at, total_cents, printed, note, items }
- `SettingsIn` / `SettingsOut` per la configurazione.

I totali (`line_total_cents`, `total_cents`) sono calcolati **lato server** a
partire dai prezzi correnti dei prodotti in DB, mai dal client.

### printer.py
- `get_printer()` → istanza escpos secondo `printer_mode` (`Usb(0x0416,0x5011,
  in_ep=0x82, out_ep=0x01)` oppure `Dummy()`).
- `render_receipt(printer, order, settings)` — scrive lo scontrino: intestazione
  associazione/evento, data/ora, numero ordine, righe (qty x nome ... totale),
  totale, messaggio finale, taglio carta.
- `print_order(order, settings)` — apre printer, renderizza, gestisce errori,
  ritorna esito. In modalità dummy ritorna anche il testo per i test.
- `test_print(settings)` — stampa di prova.

### settings.py
- `get_all(conn)` / `get(conn, key, default)` / `set(conn, key, value)`.
- `verify_pin(conn, pin)` → bool.

### main.py — API (sezione 7 del BUILD)
Prodotti: `GET /api/products`, `POST/PUT/DELETE` (PIN richiesto su scrittura).
Ordini: `POST /api/orders` (calcola totali, salva), `GET /api/orders/{id}`,
`GET /api/orders`, `POST /api/orders/{id}/print`.
Report: `GET /api/reports/sales.csv`, `GET /api/reports/summary`.
Sistema: `GET /api/health`, `POST /api/printer/test`.
Config/admin (PIN richiesto): `GET/PUT /api/settings`, `POST /api/reset` (reset
dati festa con conferma + backup prima).
Frontend: `GET /` e `GET /cassa` → index.html; `GET /admin` → admin.html;
static mount per js/css.

PIN: header `X-Admin-Pin` verificato via dependency `require_pin`. Le rotte
admin rispondono 401 se mancante/errato.

## Frontend
- **Cassa** (`index.html` + `app.js`): griglia prodotti per categoria, carrello
  con +/- e quantità, totale live, "Stampa scontrino" (POST ordine + print),
  "Annulla ordine". UI touch, pulsanti grandi.
- **Gestione** (`admin.html` + `admin.js`): sblocco con PIN, CRUD prodotti,
  attiva/disattiva, link export CSV, configurazione (nomi/messaggio/PIN), reset
  protetto da conferma, pulsante test stampa.

## Error handling
- Ordine con prodotto inesistente/non attivo → 400.
- Stampa fallita → l'ordine resta salvato (`printed=0`), l'API ritorna errore
  stampa così l'operatore può ristampare; nessuna perdita di vendita.
- PIN errato → 401.

## Testing (TDD)
pytest con DB temporaneo:
- creazione/aggiornamento/eliminazione prodotti (con/senza PIN);
- creazione ordine: totali calcolati server-side corretti, righe persistite;
- export CSV: contenuto e header corretti;
- summary report;
- printer: `render_receipt` con `Dummy` produce le sezioni attese; `print_order`
  imposta `printed=1`.

## Fuori ambito (YAGNI per v1)
Login operatori, metodo pagamento, magazzino, comanda cucina/doppia stampa, PWA
offline, coda stampa, multi-cassa con lock. Restano nella roadmap (Fase 3).
