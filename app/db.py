"""Accesso dati SQLite: connessione, schema, seed iniziale.

Unica responsabilita': fornire connessioni e gestire lo schema. Nessuna logica
applicativa (totali, stampa, ecc.) vive qui.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

# Percorso DB configurabile via env, default data/festa.sqlite3 nella root progetto.
_DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "festa.sqlite3"
DB_PATH = os.environ.get("FESTA_DB_PATH", str(_DEFAULT_DB))

SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  category TEXT NOT NULL DEFAULT 'Generale',
  price_cents INTEGER NOT NULL,
  active INTEGER NOT NULL DEFAULT 1,
  sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS orders (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT NOT NULL,
  total_cents INTEGER NOT NULL,
  printed INTEGER NOT NULL DEFAULT 0,
  note TEXT
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

CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
"""

DEFAULT_SETTINGS = {
    "association_name": "Associazione",
    "event_name": "Festa",
    "footer_message": "Grazie e arrivederci!",
    "admin_pin": "1234",
    "printer_mode": os.environ.get("FESTA_PRINTER_MODE", "dummy"),
}

DEMO_PRODUCTS = [
    # (name, category, price_cents, sort_order)
    ("Panino salamella", "Cucina", 400, 1),
    ("Patatine fritte", "Cucina", 350, 2),
    ("Piatto pasta", "Cucina", 600, 3),
    ("Acqua 0.5L", "Bibite", 100, 1),
    ("Birra media", "Bibite", 400, 2),
    ("Coca Cola", "Bibite", 250, 3),
    ("Caffe", "Bar", 100, 1),
    ("Dolce", "Bar", 250, 2),
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


def seed_defaults(conn: sqlite3.Connection) -> None:
    """Inserisce settings di default (se mancanti) e prodotti demo (se vuoto)."""
    for key, value in DEFAULT_SETTINGS.items():
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            (key, value),
        )
    count = conn.execute("SELECT COUNT(*) AS n FROM products").fetchone()["n"]
    if count == 0:
        conn.executemany(
            "INSERT INTO products (name, category, price_cents, active, sort_order) "
            "VALUES (?, ?, ?, 1, ?)",
            DEMO_PRODUCTS,
        )
    conn.commit()


def initialize(db_path: str | None = None) -> None:
    """Helper: crea schema e seed su un nuovo DB."""
    conn = get_connection(db_path)
    try:
        init_schema(conn)
        seed_defaults(conn)
    finally:
        conn.close()
