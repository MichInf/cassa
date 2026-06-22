"""FastAPI app: API REST per feste, cassa, magazzino, report, stampa + frontend.

Punto di integrazione di tutti i moduli (db, models, settings, printer).
"""
from __future__ import annotations

import csv
import io
import shutil
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app import db, printer, settings as settings_mod
from app.models import (
    EventIn,
    EventOut,
    OrderIn,
    OrderOut,
    PrintResult,
    ProductIn,
    ProductOut,
    SettingsIn,
    StockAdjust,
    StockItemIn,
    StockItemOut,
)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.initialize()
    yield


app = FastAPI(title="Festa Cassa", lifespan=lifespan)


# --- Dipendenze ---------------------------------------------------------------

def get_conn() -> sqlite3.Connection:
    conn = db.get_connection()
    try:
        yield conn
    finally:
        conn.close()


def require_pin(
    x_admin_pin: str | None = Header(default=None),
    conn: sqlite3.Connection = Depends(get_conn),
) -> None:
    if not settings_mod.verify_pin(conn, x_admin_pin):
        raise HTTPException(status_code=401, detail="PIN non valido")


# --- Helper -------------------------------------------------------------------

def _active_event_id(conn: sqlite3.Connection) -> int | None:
    row = conn.execute(
        "SELECT id FROM events WHERE active = 1 ORDER BY id LIMIT 1"
    ).fetchone()
    return row["id"] if row else None


def _require_active_event(conn: sqlite3.Connection) -> int:
    eid = _active_event_id(conn)
    if eid is None:
        raise HTTPException(status_code=409, detail="Nessuna festa attiva")
    return eid


def _event_out(row: sqlite3.Row) -> EventOut:
    return EventOut(
        id=row["id"], name=row["name"], note=row["note"],
        start_date=row["start_date"], active=bool(row["active"]),
        created_at=row["created_at"],
    )


def _product_out(row: sqlite3.Row) -> ProductOut:
    return ProductOut(
        id=row["id"], event_id=row["event_id"], name=row["name"],
        category=row["category"], price_cents=row["price_cents"],
        active=bool(row["active"]), sort_order=row["sort_order"],
    )


def _stock_out(row: sqlite3.Row) -> StockItemOut:
    return StockItemOut(
        id=row["id"], name=row["name"], category=row["category"],
        unit=row["unit"], quantity=row["quantity"], note=row["note"],
        updated_at=row["updated_at"],
    )


def _load_order(conn: sqlite3.Connection, order_id: int) -> dict:
    order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if order is None:
        raise HTTPException(status_code=404, detail="Ordine non trovato")
    items = conn.execute(
        "SELECT * FROM order_items WHERE order_id = ? ORDER BY id", (order_id,)
    ).fetchall()
    return {
        "id": order["id"],
        "event_id": order["event_id"],
        "created_at": order["created_at"],
        "total_cents": order["total_cents"],
        "printed": bool(order["printed"]),
        "note": order["note"],
        "items": [
            {
                "product_id": it["product_id"],
                "product_name": it["product_name"],
                "quantity": it["quantity"],
                "unit_price_cents": it["unit_price_cents"],
                "line_total_cents": it["line_total_cents"],
            }
            for it in items
        ],
    }


# --- API feste ----------------------------------------------------------------

@app.get("/api/events", response_model=list[EventOut])
def list_events(conn: sqlite3.Connection = Depends(get_conn)):
    rows = conn.execute(
        "SELECT * FROM events ORDER BY active DESC, id DESC"
    ).fetchall()
    return [_event_out(r) for r in rows]


@app.get("/api/events/active", response_model=EventOut | None)
def get_active_event(conn: sqlite3.Connection = Depends(get_conn)):
    eid = _active_event_id(conn)
    if eid is None:
        return None
    return _event_out(conn.execute("SELECT * FROM events WHERE id = ?", (eid,)).fetchone())


@app.post("/api/events", response_model=EventOut, dependencies=[Depends(require_pin)])
def create_event(payload: EventIn, conn: sqlite3.Connection = Depends(get_conn)):
    # La prima festa creata diventa subito attiva.
    has_any = conn.execute("SELECT COUNT(*) AS n FROM events").fetchone()["n"] > 0
    active = 0 if has_any else 1
    cur = conn.execute(
        "INSERT INTO events (name, note, start_date, active) VALUES (?, ?, ?, ?)",
        (payload.name, payload.note, payload.start_date, active),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM events WHERE id = ?", (cur.lastrowid,)).fetchone()
    return _event_out(row)


@app.put("/api/events/{event_id}", response_model=EventOut,
         dependencies=[Depends(require_pin)])
def update_event(event_id: int, payload: EventIn,
                 conn: sqlite3.Connection = Depends(get_conn)):
    if conn.execute("SELECT 1 FROM events WHERE id = ?", (event_id,)).fetchone() is None:
        raise HTTPException(status_code=404, detail="Festa non trovata")
    conn.execute(
        "UPDATE events SET name=?, note=?, start_date=? WHERE id=?",
        (payload.name, payload.note, payload.start_date, event_id),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    return _event_out(row)


@app.post("/api/events/{event_id}/activate", response_model=EventOut,
          dependencies=[Depends(require_pin)])
def activate_event(event_id: int, conn: sqlite3.Connection = Depends(get_conn)):
    if conn.execute("SELECT 1 FROM events WHERE id = ?", (event_id,)).fetchone() is None:
        raise HTTPException(status_code=404, detail="Festa non trovata")
    # Una sola festa attiva alla volta.
    conn.execute("UPDATE events SET active = 0")
    conn.execute("UPDATE events SET active = 1 WHERE id = ?", (event_id,))
    conn.commit()
    row = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    return _event_out(row)


@app.delete("/api/events/{event_id}", dependencies=[Depends(require_pin)])
def delete_event(event_id: int, conn: sqlite3.Connection = Depends(get_conn)):
    if conn.execute("SELECT 1 FROM events WHERE id = ?", (event_id,)).fetchone() is None:
        raise HTTPException(status_code=404, detail="Festa non trovata")
    has_orders = conn.execute(
        "SELECT 1 FROM orders WHERE event_id = ? LIMIT 1", (event_id,)
    ).fetchone()
    if has_orders:
        raise HTTPException(
            status_code=400,
            detail="Festa con ordini registrati: non eliminabile (usa l'archivio)",
        )
    conn.execute("DELETE FROM products WHERE event_id = ?", (event_id,))
    conn.execute("DELETE FROM events WHERE id = ?", (event_id,))
    conn.commit()
    return {"ok": True}


# --- API prodotti -------------------------------------------------------------

@app.get("/api/products", response_model=list[ProductOut])
def list_products(
    event_id: int | None = Query(default=None),
    conn: sqlite3.Connection = Depends(get_conn),
):
    """Prodotti di una festa. Senza event_id usa la festa attiva."""
    eid = event_id if event_id is not None else _active_event_id(conn)
    if eid is None:
        return []
    rows = conn.execute(
        "SELECT * FROM products WHERE event_id = ? ORDER BY category, sort_order, name",
        (eid,),
    ).fetchall()
    return [_product_out(r) for r in rows]


@app.post("/api/products", response_model=ProductOut, dependencies=[Depends(require_pin)])
def create_product(payload: ProductIn, conn: sqlite3.Connection = Depends(get_conn)):
    eid = payload.event_id if payload.event_id is not None else _require_active_event(conn)
    if conn.execute("SELECT 1 FROM events WHERE id = ?", (eid,)).fetchone() is None:
        raise HTTPException(status_code=400, detail="Festa inesistente")
    cur = conn.execute(
        "INSERT INTO products (event_id, name, category, price_cents, active, sort_order) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (eid, payload.name, payload.category, payload.price_cents,
         int(payload.active), payload.sort_order),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM products WHERE id = ?", (cur.lastrowid,)).fetchone()
    return _product_out(row)


@app.put("/api/products/{product_id}", response_model=ProductOut,
         dependencies=[Depends(require_pin)])
def update_product(product_id: int, payload: ProductIn,
                   conn: sqlite3.Connection = Depends(get_conn)):
    row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Prodotto non trovato")
    # event_id non si sposta in update se non specificato.
    eid = payload.event_id if payload.event_id is not None else row["event_id"]
    conn.execute(
        "UPDATE products SET name=?, category=?, price_cents=?, active=?, sort_order=?, "
        "event_id=? WHERE id=?",
        (payload.name, payload.category, payload.price_cents,
         int(payload.active), payload.sort_order, eid, product_id),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    return _product_out(row)


@app.delete("/api/products/{product_id}", dependencies=[Depends(require_pin)])
def delete_product(product_id: int, conn: sqlite3.Connection = Depends(get_conn)):
    if conn.execute("SELECT 1 FROM products WHERE id = ?", (product_id,)).fetchone() is None:
        raise HTTPException(status_code=404, detail="Prodotto non trovato")
    conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
    conn.commit()
    return {"ok": True}


# --- API ordini ---------------------------------------------------------------

@app.post("/api/orders", response_model=OrderOut)
def create_order(payload: OrderIn, conn: sqlite3.Connection = Depends(get_conn)):
    """Crea un ordine sulla festa attiva. Prezzi/totali calcolati server-side."""
    eid = _require_active_event(conn)
    created_at = datetime.now().isoformat(timespec="seconds")
    items_out = []
    total = 0
    for item in payload.items:
        prod = conn.execute(
            "SELECT * FROM products WHERE id = ?", (item.product_id,)
        ).fetchone()
        if prod is None or not prod["active"]:
            raise HTTPException(
                status_code=400,
                detail=f"Prodotto {item.product_id} inesistente o non attivo",
            )
        if prod["event_id"] != eid:
            raise HTTPException(
                status_code=400,
                detail=f"Prodotto {item.product_id} non appartiene alla festa attiva",
            )
        unit = prod["price_cents"]
        line_total = unit * item.quantity
        total += line_total
        items_out.append({
            "product_id": prod["id"],
            "product_name": prod["name"],
            "quantity": item.quantity,
            "unit_price_cents": unit,
            "line_total_cents": line_total,
        })

    cur = conn.execute(
        "INSERT INTO orders (event_id, created_at, total_cents, printed, note) "
        "VALUES (?, ?, ?, 0, ?)",
        (eid, created_at, total, payload.note),
    )
    order_id = cur.lastrowid
    for it in items_out:
        conn.execute(
            "INSERT INTO order_items (order_id, product_id, product_name, quantity, "
            "unit_price_cents, line_total_cents) VALUES (?, ?, ?, ?, ?, ?)",
            (order_id, it["product_id"], it["product_name"], it["quantity"],
             it["unit_price_cents"], it["line_total_cents"]),
        )
    conn.commit()
    return _load_order(conn, order_id)


@app.get("/api/orders", response_model=list[OrderOut])
def list_orders(
    event_id: int | None = Query(default=None),
    conn: sqlite3.Connection = Depends(get_conn),
):
    eid = event_id if event_id is not None else _active_event_id(conn)
    if eid is None:
        rows = conn.execute("SELECT id FROM orders ORDER BY id DESC").fetchall()
    else:
        rows = conn.execute(
            "SELECT id FROM orders WHERE event_id = ? ORDER BY id DESC", (eid,)
        ).fetchall()
    return [_load_order(conn, r["id"]) for r in rows]


@app.get("/api/orders/{order_id}", response_model=OrderOut)
def get_order(order_id: int, conn: sqlite3.Connection = Depends(get_conn)):
    return _load_order(conn, order_id)


@app.post("/api/orders/{order_id}/print", response_model=PrintResult)
def print_order(order_id: int, conn: sqlite3.Connection = Depends(get_conn)):
    order = _load_order(conn, order_id)
    cfg = settings_mod.get_all(conn)
    cfg["event_name"] = _event_name_for(conn, order["event_id"])
    result = printer.print_order(order, cfg)
    if result.get("ok"):
        conn.execute("UPDATE orders SET printed = 1 WHERE id = ?", (order_id,))
        conn.commit()
    return PrintResult(**result)


def _event_name_for(conn: sqlite3.Connection, event_id: int | None) -> str:
    if event_id is None:
        return ""
    row = conn.execute("SELECT name FROM events WHERE id = ?", (event_id,)).fetchone()
    return row["name"] if row else ""


# --- API magazzino (scollegato dalla cassa) -----------------------------------

@app.get("/api/stock", response_model=list[StockItemOut])
def list_stock(conn: sqlite3.Connection = Depends(get_conn)):
    rows = conn.execute(
        "SELECT * FROM stock_items ORDER BY category, name"
    ).fetchall()
    return [_stock_out(r) for r in rows]


@app.post("/api/stock", response_model=StockItemOut, dependencies=[Depends(require_pin)])
def create_stock(payload: StockItemIn, conn: sqlite3.Connection = Depends(get_conn)):
    cur = conn.execute(
        "INSERT INTO stock_items (name, category, unit, quantity, note, updated_at) "
        "VALUES (?, ?, ?, ?, ?, datetime('now'))",
        (payload.name, payload.category, payload.unit, payload.quantity, payload.note),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM stock_items WHERE id = ?", (cur.lastrowid,)).fetchone()
    return _stock_out(row)


@app.put("/api/stock/{item_id}", response_model=StockItemOut,
         dependencies=[Depends(require_pin)])
def update_stock(item_id: int, payload: StockItemIn,
                 conn: sqlite3.Connection = Depends(get_conn)):
    if conn.execute("SELECT 1 FROM stock_items WHERE id = ?", (item_id,)).fetchone() is None:
        raise HTTPException(status_code=404, detail="Articolo non trovato")
    conn.execute(
        "UPDATE stock_items SET name=?, category=?, unit=?, quantity=?, note=?, "
        "updated_at=datetime('now') WHERE id=?",
        (payload.name, payload.category, payload.unit, payload.quantity,
         payload.note, item_id),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM stock_items WHERE id = ?", (item_id,)).fetchone()
    return _stock_out(row)


@app.post("/api/stock/{item_id}/adjust", response_model=StockItemOut,
          dependencies=[Depends(require_pin)])
def adjust_stock(item_id: int, payload: StockAdjust,
                 conn: sqlite3.Connection = Depends(get_conn)):
    """Rettifica scorte (carico/scarico manuale) sommando un delta +/-."""
    row = conn.execute("SELECT * FROM stock_items WHERE id = ?", (item_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Articolo non trovato")
    new_qty = row["quantity"] + payload.delta
    conn.execute(
        "UPDATE stock_items SET quantity=?, updated_at=datetime('now') WHERE id=?",
        (new_qty, item_id),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM stock_items WHERE id = ?", (item_id,)).fetchone()
    return _stock_out(row)


@app.delete("/api/stock/{item_id}", dependencies=[Depends(require_pin)])
def delete_stock(item_id: int, conn: sqlite3.Connection = Depends(get_conn)):
    if conn.execute("SELECT 1 FROM stock_items WHERE id = ?", (item_id,)).fetchone() is None:
        raise HTTPException(status_code=404, detail="Articolo non trovato")
    conn.execute("DELETE FROM stock_items WHERE id = ?", (item_id,))
    conn.commit()
    return {"ok": True}


# --- Report -------------------------------------------------------------------

@app.get("/api/reports/sales.csv")
def sales_csv(
    event_id: int | None = Query(default=None),
    conn: sqlite3.Connection = Depends(get_conn),
):
    eid = event_id if event_id is not None else _active_event_id(conn)
    query = (
        "SELECT orders.id AS order_id, orders.created_at, order_items.product_name, "
        "order_items.quantity, order_items.unit_price_cents, order_items.line_total_cents "
        "FROM order_items JOIN orders ON orders.id = order_items.order_id "
    )
    params: tuple = ()
    if eid is not None:
        query += "WHERE orders.event_id = ? "
        params = (eid,)
    query += "ORDER BY orders.id ASC"
    rows = conn.execute(query, params).fetchall()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "order_id", "created_at", "product_name", "quantity",
        "unit_price_cents", "line_total_cents",
    ])
    for r in rows:
        writer.writerow([
            r["order_id"], r["created_at"], r["product_name"],
            r["quantity"], r["unit_price_cents"], r["line_total_cents"],
        ])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=vendite.csv"},
    )


@app.get("/api/reports/summary")
def summary(
    event_id: int | None = Query(default=None),
    conn: sqlite3.Connection = Depends(get_conn),
):
    eid = event_id if event_id is not None else _active_event_id(conn)
    where = "WHERE event_id = ?" if eid is not None else ""
    params: tuple = (eid,) if eid is not None else ()
    agg = conn.execute(
        f"SELECT COUNT(*) AS orders_count, COALESCE(SUM(total_cents), 0) AS total_cents "
        f"FROM orders {where}",
        params,
    ).fetchone()
    if eid is not None:
        top = conn.execute(
            "SELECT product_name, SUM(quantity) AS qty, SUM(line_total_cents) AS revenue_cents "
            "FROM order_items JOIN orders ON orders.id = order_items.order_id "
            "WHERE orders.event_id = ? GROUP BY product_name ORDER BY qty DESC LIMIT 10",
            (eid,),
        ).fetchall()
    else:
        top = conn.execute(
            "SELECT product_name, SUM(quantity) AS qty, SUM(line_total_cents) AS revenue_cents "
            "FROM order_items GROUP BY product_name ORDER BY qty DESC LIMIT 10"
        ).fetchall()
    return {
        "event_id": eid,
        "orders_count": agg["orders_count"],
        "total_cents": agg["total_cents"],
        "top_products": [
            {"product_name": r["product_name"], "qty": r["qty"],
             "revenue_cents": r["revenue_cents"]}
            for r in top
        ],
    }


# --- Settings / sistema -------------------------------------------------------

@app.get("/api/settings")
def get_settings(conn: sqlite3.Connection = Depends(get_conn)):
    return settings_mod.get_public(conn)


@app.put("/api/settings", dependencies=[Depends(require_pin)])
def update_settings(payload: SettingsIn, conn: sqlite3.Connection = Depends(get_conn)):
    values = {k: v for k, v in payload.model_dump().items() if v is not None}
    settings_mod.update_many(conn, values)
    return settings_mod.get_public(conn)


@app.post("/api/reset", dependencies=[Depends(require_pin)])
def reset_event(payload: dict, conn: sqlite3.Connection = Depends(get_conn)):
    """Azzera gli ordini della festa attiva (backup automatico prima)."""
    if not payload.get("confirm"):
        raise HTTPException(status_code=400, detail="Conferma mancante")
    eid = _require_active_event(conn)
    backup_path = None
    try:
        src = Path(db.DB_PATH)
        if src.exists():
            backups = src.parent.parent / "backups"
            backups.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup_path = backups / f"festa-{stamp}.sqlite3"
            shutil.copy2(src, backup_path)
    except Exception:
        backup_path = None
    conn.execute(
        "DELETE FROM order_items WHERE order_id IN "
        "(SELECT id FROM orders WHERE event_id = ?)",
        (eid,),
    )
    conn.execute("DELETE FROM orders WHERE event_id = ?", (eid,))
    conn.commit()
    return {"ok": True, "backup": str(backup_path) if backup_path else None}


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/printer/test", response_model=PrintResult,
          dependencies=[Depends(require_pin)])
def printer_test(conn: sqlite3.Connection = Depends(get_conn)):
    cfg = settings_mod.get_all(conn)
    cfg["event_name"] = _event_name_for(conn, _active_event_id(conn))
    return PrintResult(**printer.test_print(cfg))


# --- Frontend statico ---------------------------------------------------------

@app.get("/")
@app.get("/cassa")
def cassa_page():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/admin")
def admin_page():
    return FileResponse(STATIC_DIR / "admin.html")


if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
