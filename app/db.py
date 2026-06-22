"""Accesso dati SQLite: connessione, schema, migrazioni, seed iniziale.

Modello v2:
- events       : le feste (una sola attiva alla volta)
- products     : prodotti cassa, specifici per festa (event_id)
- orders       : ordini, legati alla festa (event_id)
- order_items  : righe ordine
- stock_items  : magazzino, lista separata e GLOBALE, scollegata dalla cassa
- settings     : configurazione (chiave/valore)
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

_DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "festa.sqlite3"
DB_PATH = os.environ.get("FESTA_DB_PATH", str(_DEFAULT_DB))

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  note TEXT,
  start_date TEXT,
  active INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS products (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id INTEGER,
  name TEXT NOT NULL,
  category TEXT NOT NULL DEFAULT 'Generale',
  price_cents INTEGER NOT NULL,
  active INTEGER NOT NULL DEFAULT 1,
  sort_order INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY(event_id) REFERENCES events(id)
);

CREATE TABLE IF NOT EXISTS orders (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id INTEGER,
  created_at TEXT NOT NULL,
  total_cents INTEGER NOT NULL,
  printed INTEGER NOT NULL DEFAULT 0,
  note TEXT,
  FOREIGN KEY(event_id) REFERENCES events(id)
);

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

CREATE TABLE IF NOT EXISTS stock_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  category TEXT NOT NULL DEFAULT 'Generale',
  unit TEXT NOT NULL DEFAULT 'pz',
  quantity REAL NOT NULL DEFAULT 0,
  note TEXT,
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
"""

DEFAULT_SETTINGS = {
    "association_name": "Associazione",
    "footer_message": "Grazie e arrivederci!",
    "admin_pin": "1234",
    "printer_mode": os.environ.get("FESTA_PRINTER_MODE", "dummy"),
}

DEFAULT_EVENT_NAME = "Festa di prova"

# Prodotti demo della festa di default: (name, category, price_cents, sort_order)
DEMO_PRODUCTS = [
    ("Panino salamella", "Cucina", 400, 1),
    ("Patatine fritte", "Cucina", 350, 2),
    ("Piatto pasta", "Cucina", 600, 3),
    ("Acqua 0.5L", "Bibite", 100, 1),
    ("Birra media", "Bibite", 400, 2),
    ("Spritz", "Cocktail", 500, 1),
    ("Gin Tonic", "Cocktail", 600, 2),
]

# Magazzino demo (scollegato dalla cassa): (name, category, unit, quantity)
DEMO_STOCK = [
    ("Bottiglia Gin", "Alcolici", "bottiglia", 6),
    ("Bottiglia Vodka", "Alcolici", "bottiglia", 4),
    ("Acqua tonica", "Bibite", "lattina", 48),
    ("Bicchieri plastica", "Materiale", "pz", 500),
]


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    """Ritorna una connessione con row factory dict-like e foreign keys attive."""
    path = db_path or DB_PATH
    parent = Path(path).parent
    if str(parent) and not parent.exists():
        parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    """Crea le tabelle se non esistono."""
    conn.executescript(SCHEMA)
    conn.commit()


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}


def migrate(conn: sqlite3.Connection) -> None:
    """Migrazioni idempotenti per DB pre-esistenti (aggiunge colonne mancanti)."""
    prod_cols = _columns(conn, "products")
    if "event_id" not in prod_cols:
        conn.execute("ALTER TABLE products ADD COLUMN event_id INTEGER")
    order_cols = _columns(conn, "orders")
    if "event_id" not in order_cols:
        conn.execute("ALTER TABLE orders ADD COLUMN event_id INTEGER")
    conn.commit()


def _ensure_active_event(conn: sqlite3.Connection) -> int:
    """Garantisce l'esistenza di una festa attiva e ne ritorna l'id."""
    row = conn.execute(
        "SELECT id FROM events WHERE active = 1 ORDER BY id LIMIT 1"
    ).fetchone()
    if row:
        return row["id"]
    # nessuna attiva: se ne esiste una qualsiasi attivala, altrimenti creala
    row = conn.execute("SELECT id FROM events ORDER BY id LIMIT 1").fetchone()
    if row:
        conn.execute("UPDATE events SET active = 1 WHERE id = ?", (row["id"],))
        conn.commit()
        return row["id"]
    cur = conn.execute(
        "INSERT INTO events (name, active, start_date) VALUES (?, 1, date('now'))",
        (DEFAULT_EVENT_NAME,),
    )
    conn.commit()
    return cur.lastrowid


def seed_defaults(conn: sqlite3.Connection) -> None:
    """Inserisce settings, festa di default, prodotti e magazzino demo se vuoti."""
    for key, value in DEFAULT_SETTINGS.items():
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            (key, value),
        )

    event_id = _ensure_active_event(conn)

    # Backfill: righe orfane (event_id NULL) vanno alla festa attiva.
    conn.execute(
        "UPDATE products SET event_id = ? WHERE event_id IS NULL", (event_id,)
    )
    conn.execute(
        "UPDATE orders SET event_id = ? WHERE event_id IS NULL", (event_id,)
    )

    n_products = conn.execute(
        "SELECT COUNT(*) AS n FROM products WHERE event_id = ?", (event_id,)
    ).fetchone()["n"]
    if n_products == 0:
        conn.executemany(
            "INSERT INTO products (event_id, name, category, price_cents, active, "
            "sort_order) VALUES (?, ?, ?, ?, 1, ?)",
            [(event_id, n, c, p, s) for (n, c, p, s) in DEMO_PRODUCTS],
        )

    n_stock = conn.execute("SELECT COUNT(*) AS n FROM stock_items").fetchone()["n"]
    if n_stock == 0:
        conn.executemany(
            "INSERT INTO stock_items (name, category, unit, quantity) "
            "VALUES (?, ?, ?, ?)",
            DEMO_STOCK,
        )
    conn.commit()


def initialize(db_path: str | None = None) -> None:
    """Helper: crea schema, applica migrazioni e seed."""
    conn = get_connection(db_path)
    try:
        init_schema(conn)
        migrate(conn)
        seed_defaults(conn)
    finally:
        conn.close()
