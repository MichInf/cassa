"""Fixture condivise per i test: DB temporaneo e TestClient isolato."""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture()
def db_path(tmp_path):
    """Percorso a un DB SQLite temporaneo, inizializzato con schema + demo."""
    path = tmp_path / "test.sqlite3"
    os.environ["FESTA_DB_PATH"] = str(path)
    os.environ["FESTA_PRINTER_MODE"] = "dummy"
    # import dopo aver settato l'env cosi' DB_PATH lo recepisce
    import importlib

    from app import db as db_module

    importlib.reload(db_module)
    db_module.initialize(str(path))
    return str(path)


@pytest.fixture()
def conn(db_path):
    from app import db as db_module

    connection = db_module.get_connection(db_path)
    yield connection
    connection.close()


@pytest.fixture()
def client(db_path):
    """TestClient FastAPI con DB temporaneo gia' inizializzato."""
    import importlib

    from fastapi.testclient import TestClient

    import app.main as main_module

    importlib.reload(main_module)
    with TestClient(main_module.app) as c:
        yield c


@pytest.fixture()
def admin_headers():
    """Header con PIN admin di default (1234)."""
    return {"X-Admin-Pin": "1234"}
