"""Inizializza il database: crea schema e inserisce dati demo.

Uso:
    python scripts/init_db.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import db  # noqa: E402


def main() -> None:
    db.initialize()
    print(f"Database inizializzato: {db.DB_PATH}")


if __name__ == "__main__":
    main()
