"""Test delle API FastAPI con DB temporaneo (vedi conftest.py)."""

N_DEMO_PRODUCTS = 7


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# --- Feste --------------------------------------------------------------------

def test_active_event_seeded(client):
    r = client.get("/api/events/active")
    assert r.status_code == 200
    assert r.json() is not None
    assert r.json()["active"] is True


def test_create_event_opens_it(client, admin_headers):
    # senza PIN -> 401
    assert client.post("/api/events", json={"name": "Sagra"}).status_code == 401
    # creare una festa la apre (diventa l'unica attiva)
    r = client.post("/api/events", json={"name": "Sagra 2026", "note": "test"},
                    headers=admin_headers)
    assert r.status_code == 200
    new_id = r.json()["id"]
    assert r.json()["active"] is True
    assert client.get("/api/events/active").json()["id"] == new_id
    # la festa di default precedente ora e' chiusa
    events = {e["id"]: e for e in client.get("/api/events").json()}
    assert sum(1 for e in events.values() if e["active"]) == 1
    # la nuova festa non ha prodotti
    assert client.get("/api/products").json() == []


def test_close_event(client, admin_headers):
    active = client.get("/api/events/active").json()
    r = client.post(f"/api/events/{active['id']}/close", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["active"] is False
    # nessuna festa aperta: la cassa non puo' creare ordini
    assert client.get("/api/events/active").json() is None
    p_fake = {"items": [{"product_id": 1, "quantity": 1}]}
    assert client.post("/api/orders", json=p_fake).status_code == 409


def test_delete_event_with_orders_blocked(client, admin_headers):
    active = client.get("/api/events/active").json()
    products = client.get("/api/products").json()
    client.post("/api/orders",
                json={"items": [{"product_id": products[0]["id"], "quantity": 1}]})
    r = client.delete(f"/api/events/{active['id']}", headers=admin_headers)
    assert r.status_code == 400


# --- Prodotti (per festa) -----------------------------------------------------

def test_list_products_seeded(client):
    data = client.get("/api/products").json()
    assert len(data) == N_DEMO_PRODUCTS
    assert all(p["event_id"] is not None for p in data)


def test_create_product_requires_pin(client):
    body = {"name": "Test", "category": "X", "price_cents": 150}
    assert client.post("/api/products", json=body).status_code == 401
    assert client.post("/api/products", json=body,
                       headers={"X-Admin-Pin": "0000"}).status_code == 401


def test_product_crud_scoped_to_active_event(client, admin_headers):
    active = client.get("/api/events/active").json()
    body = {"name": "Spritz", "category": "Bar", "price_cents": 500}
    r = client.post("/api/products", json=body, headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["event_id"] == active["id"]
    pid = r.json()["id"]

    r = client.put(f"/api/products/{pid}",
                   json={**body, "price_cents": 550}, headers=admin_headers)
    assert r.json()["price_cents"] == 550

    assert client.delete(f"/api/products/{pid}", headers=admin_headers).status_code == 200


# --- Ordini -------------------------------------------------------------------

def test_create_order_computes_totals_server_side(client):
    p1 = client.get("/api/products").json()[0]
    body = {"items": [{"product_id": p1["id"], "quantity": 2}], "note": "tavolo 3"}
    order = client.post("/api/orders", json=body).json()
    assert order["total_cents"] == p1["price_cents"] * 2
    assert order["event_id"] is not None
    assert order["printed"] is False


def test_order_uses_active_event_products_only(client, admin_headers):
    # prodotto della festa di default (prima di aprirne un'altra)
    pid = client.get("/api/products").json()[0]["id"]
    # creare una nuova festa la apre (chiude la default): resta senza prodotti
    client.post("/api/events", json={"name": "Altra"}, headers=admin_headers)
    # ordinare un prodotto della festa chiusa -> 400
    r = client.post("/api/orders", json={"items": [{"product_id": pid, "quantity": 1}]})
    assert r.status_code == 400


def test_order_print_sets_printed(client):
    products = client.get("/api/products").json()
    order = client.post(
        "/api/orders", json={"items": [{"product_id": products[0]["id"], "quantity": 1}]}
    ).json()
    r = client.post(f"/api/orders/{order['id']}/print")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert client.get(f"/api/orders/{order['id']}").json()["printed"] is True


# --- Magazzino ----------------------------------------------------------------

def test_stock_seeded(client):
    data = client.get("/api/stock").json()
    assert len(data) >= 1
    assert all("quantity" in s for s in data)


def test_stock_crud_and_adjust(client, admin_headers):
    assert client.post("/api/stock", json={"name": "Rum"}).status_code == 401
    r = client.post("/api/stock",
                    json={"name": "Bottiglia Rum", "category": "Alcolici",
                          "unit": "bottiglia", "quantity": 3}, headers=admin_headers)
    assert r.status_code == 200
    sid = r.json()["id"]
    assert r.json()["quantity"] == 3

    # rettifica: scarico 2
    r = client.post(f"/api/stock/{sid}/adjust", json={"delta": -2}, headers=admin_headers)
    assert r.json()["quantity"] == 1

    r = client.put(f"/api/stock/{sid}",
                   json={"name": "Rum scuro", "quantity": 10}, headers=admin_headers)
    assert r.json()["name"] == "Rum scuro"
    assert r.json()["quantity"] == 10

    assert client.delete(f"/api/stock/{sid}", headers=admin_headers).status_code == 200


def test_stock_is_independent_from_sales(client):
    """Vendere un prodotto cassa NON deve toccare il magazzino."""
    before = client.get("/api/stock").json()
    products = client.get("/api/products").json()
    client.post("/api/orders",
                json={"items": [{"product_id": products[0]["id"], "quantity": 5}]})
    after = client.get("/api/stock").json()
    assert before == after


# --- Report / settings --------------------------------------------------------

def test_sales_csv(client):
    products = client.get("/api/products").json()
    client.post("/api/orders",
                json={"items": [{"product_id": products[0]["id"], "quantity": 3}]})
    r = client.get("/api/reports/sales.csv")
    assert r.status_code == 200
    assert "order_id,created_at,product_name" in r.text
    assert products[0]["name"] in r.text


def test_summary_scoped_to_active_event(client):
    products = client.get("/api/products").json()
    client.post("/api/orders",
                json={"items": [{"product_id": products[0]["id"], "quantity": 2}]})
    data = client.get("/api/reports/summary").json()
    assert data["orders_count"] == 1
    assert data["total_cents"] == products[0]["price_cents"] * 2


def test_settings_get_hides_pin(client):
    r = client.get("/api/settings")
    assert "admin_pin" not in r.json()
    assert r.json()["association_name"] == "Associazione"


def test_settings_update_requires_pin(client, admin_headers):
    assert client.put("/api/settings",
                      json={"association_name": "X"}).status_code == 401
    r = client.put("/api/settings",
                   json={"association_name": "Pro Loco"}, headers=admin_headers)
    assert r.status_code == 200
    assert client.get("/api/settings").json()["association_name"] == "Pro Loco"


def test_reset_clears_active_event_orders(client, admin_headers):
    products = client.get("/api/products").json()
    client.post("/api/orders",
                json={"items": [{"product_id": products[0]["id"], "quantity": 1}]})
    assert client.post("/api/reset", json={"confirm": True}).status_code == 401
    assert client.post("/api/reset", json={"confirm": False},
                       headers=admin_headers).status_code == 400
    r = client.post("/api/reset", json={"confirm": True}, headers=admin_headers)
    assert r.status_code == 200
    assert client.get("/api/reports/summary").json()["orders_count"] == 0
