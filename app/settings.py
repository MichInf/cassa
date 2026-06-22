"""Lettura/scrittura della tabella settings e verifica del PIN admin."""
from __future__ import annotations

import sqlite3

# Chiavi non esposte in lettura tramite get_public().
SECRET_KEYS = {"admin_pin"}


def get_all(conn: sqlite3.Connection) -> dict[str, str]:
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    return {row["key"]: row["value"] for row in rows}


def get_public(conn: sqlite3.Connection) -> dict[str, str]:
    """Settings senza i valori segreti (es. admin_pin)."""
    return {k: v for k, v in get_all(conn).items() if k not in SECRET_KEYS}


def get(conn: sqlite3.Connection, key: str, default: str | None = None) -> str | None:
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_value(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    conn.commit()


def update_many(conn: sqlite3.Connection, values: dict[str, str]) -> None:
    for key, value in values.items():
        if value is None:
            continue
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(value)),
        )
    conn.commit()


def verify_pin(conn: sqlite3.Connection, pin: str | None) -> bool:
    if not pin:
        return False
    stored = get(conn, "admin_pin")
    return stored is not None and pin == stored
