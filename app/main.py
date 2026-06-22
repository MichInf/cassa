"""FastAPI app: API REST per cassa, gestione, report, stampa + frontend statico.

Punto di integrazione di tutti i moduli (db, models, settings, printer).
"""
from __future__ import annotations

import csv
import io
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app import db, printer, settings as settings_mod
from app.models import (
    OrderIn,
    OrderOut,
    PrintResult,
    ProductIn,
    ProductOut,
    SettingsIn,
)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Garantisce schema e dati di default all'avvio.
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
    """Verifica il PIN admin; solleva 401 se mancante o errato."""
    if not settings_mod.verify_pin(conn, x_admin_pin):
        raise HTTPException(status_code=401, detail="PIN non valido")


# --- Helper -------------------------------------------------------------------

def _product_row_to_out(row: sqlite3.Row) -> ProductOut:
    return ProductOut(
        id=row["id"],
        name=row["name"],
        category=row["category"],
        price_cents=row["price_cents"],
        active=bool(row["active"]),
        sort_order=row["sort_order"],
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


# --- API prodotti -------------------------------------------------------------

@app.get("/api/products", response_model=list[ProductOut])
def list_products(conn: sqlite3.Connection = Depends(get_conn)):
    rows = conn.execute(
        "SELECT * FROM products ORDER BY category, sort_order, name"
    ).fetchall()
    return [_product_row_to_out(r) for r in rows]


@app.post("/api/products", response_model=ProductOut, dependencies=[Depends(require_pin)])
def create_product(payload: ProductIn, conn: sqlite3.Connection = Depends(get_conn)):
    cur = conn.execute(
        "INSERT INTO products (name, category, price_cents, active, sort_order) "
        "VALUES (?, ?, ?, ?, ?)",
        (payload.name, payload.category, payload.price_cents,
         int(payload.active), payload.sort_order),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM products WHERE id = ?", (cur.lastrowid,)).fetchone()
    return _product_row_to_out(row)


@app.put("/api/products/{product_id}", response_model=ProductOut,
         dependencies=[Depends(require_pin)])
def update_product(product_id: int, payload: ProductIn,
                   conn: sqlite3.Connection = Depends(get_conn)):
    exists = conn.execute("SELECT 1 FROM products WHERE id = ?", (product_id,)).fetchone()
    if exists is None:
        raise HTTPException(status_code=404, detail="Prodotto non trovato")
    conn.execute(
        "UPDATE products SET name=?, category=?, price_cents=?, active=?, sort_order=? "
        "WHERE id=?",
        (payload.name, payload.category, payload.price_cents,
         int(payload.active), payload.sort_order, product_id),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    return _product_row_to_out(row)


@app.delete("/api/products/{product_id}", dependencies=[Depends(require_pin)])
def delete_product(product_id: int, conn: sqlite3.Connection = Depends(get_conn)):
    exists = conn.execute("SELECT 1 FROM products WHERE id = ?", (product_id,)).fetchone()
    if exists is None:
        raise HTTPException(status_code=404, detail="Prodotto non trovato")
    conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
    conn.commit()
    return {"ok": True}


# --- API ordini ---------------------------------------------------------------

@app.post("/api/orders", response_model=OrderOut)
def create_order(payload: OrderIn, conn: sqlite3.Connection = Depends(get_conn)):
    """Crea un ordine. I prezzi/totali sono calcolati server-side dal DB."""
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
        "INSERT INTO orders (created_at, total_cents, printed, note) VALUES (?, ?, 0, ?)",
        (created_at, total, payload.note),
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
def list_orders(conn: sqlite3.Connection = Depends(get_conn)):
    rows = conn.execute("SELECT id FROM orders ORDER BY id DESC").fetchall()
    return [_load_order(conn, r["id"]) for r in rows]


@app.get("/api/orders/{order_id}", response_model=OrderOut)
def get_order(order_id: int, conn: sqlite3.Connection = Depends(get_conn)):
    return _load_order(conn, order_id)


@app.post("/api/orders/{order_id}/print", response_model=PrintResult)
def print_order(order_id: int, conn: sqlite3.Connection = Depends(get_conn)):
    order = _load_order(conn, order_id)
    cfg = settings_mod.get_all(conn)
    result = printer.print_order(order, cfg)
    if result.get("ok"):
        conn.execute("UPDATE orders SET printed = 1 WHERE id = ?", (order_id,))
        conn.commit()
    return PrintResult(**result)


# --- Report -------------------------------------------------------------------

@app.get("/api/reports/sales.csv")
def sales_csv(conn: sqlite3.Connection = Depends(get_conn)):
    rows = conn.execute(
        "SELECT orders.id AS order_id, orders.created_at, order_items.product_name, "
        "order_items.quantity, order_items.unit_price_cents, order_items.line_total_cents "
        "FROM order_items JOIN orders ON orders.id = order_items.order_id "
        "ORDER BY orders.id ASC"
    ).fetchall()
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
def summary(conn: sqlite3.Connection = Depends(get_conn)):
    agg = conn.execute(
        "SELECT COUNT(*) AS orders_count, COALESCE(SUM(total_cents), 0) AS total_cents "
        "FROM orders"
    ).fetchone()
    top = conn.execute(
        "SELECT product_name, SUM(quantity) AS qty, SUM(line_total_cents) AS revenue_cents "
        "FROM order_items GROUP BY product_name ORDER BY qty DESC LIMIT 10"
    ).fetchall()
    return {
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
    if not payload.get("confirm"):
        raise HTTPException(status_code=400, detail="Conferma mancante")
    # Backup di sicurezza prima del reset.
    backup_path = None
    try:
        src = Path(db.DB_PATH)
        if src.exists():
            backups = src.parent.parent / "backups"
            backups.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup_path = backups / f"festa-{stamp}.sqlite3"
            shutil.copy2(src, backup_path)
    except Exception:  # il backup non deve bloccare il reset, ma lo segnaliamo
        backup_path = None
    conn.execute("DELETE FROM order_items")
    conn.execute("DELETE FROM orders")
    conn.commit()
    return {"ok": True, "backup": str(backup_path) if backup_path else None}


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/printer/test", response_model=PrintResult,
          dependencies=[Depends(require_pin)])
def printer_test(conn: sqlite3.Connection = Depends(get_conn)):
    cfg = settings_mod.get_all(conn)
    return PrintResult(**printer.test_print(cfg))


# --- Frontend statico ---------------------------------------------------------

@app.get("/")
@app.get("/cassa")
def cassa_page():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/admin")
def admin_page():
    return FileResponse(STATIC_DIR / "admin.html")


# Mount degli asset statici (js/css). Montato per ultimo per non oscurare le API.
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
