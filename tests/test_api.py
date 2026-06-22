"""Test delle API FastAPI con DB temporaneo (vedi conftest.py)."""


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_list_products_seeded(client):
    r = client.get("/api/products")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 8
    assert all("price_cents" in p for p in data)


def test_create_product_requires_pin(client):
    body = {"name": "Test", "category": "X", "price_cents": 150}
    # senza PIN -> 401
    assert client.post("/api/products", json=body).status_code == 401
    # PIN errato -> 401
    assert client.post(
        "/api/products", json=body, headers={"X-Admin-Pin": "0000"}
    ).status_code == 401


def test_product_crud(client, admin_headers):
    body = {"name": "Spritz", "category": "Bar", "price_cents": 500,
            "active": True, "sort_order": 9}
    r = client.post("/api/products", json=body, headers=admin_headers)
    assert r.status_code == 200
    pid = r.json()["id"]
    assert r.json()["price_cents"] == 500

    r = client.put(f"/api/products/{pid}",
                   json={**body, "price_cents": 550}, headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["price_cents"] == 550

    r = client.delete(f"/api/products/{pid}", headers=admin_headers)
    assert r.status_code == 200
    assert client.get(f"/api/products").status_code == 200


def test_create_order_computes_totals_server_side(client):
    products = client.get("/api/products").json()
    p1 = products[0]
    # invio un prezzo "falso" non e' possibile: l'API accetta solo product_id+quantity
    body = {"items": [{"product_id": p1["id"], "quantity": 2}], "note": "tavolo 3"}
    r = client.post("/api/orders", json=body)
    assert r.status_code == 200
    order = r.json()
    assert order["total_cents"] == p1["price_cents"] * 2
    assert order["items"][0]["line_total_cents"] == p1["price_cents"] * 2
    assert order["printed"] is False
    assert order["note"] == "tavolo 3"


def test_create_order_rejects_inactive_product(client, admin_headers):
    products = client.get("/api/products").json()
    pid = products[0]["id"]
    # disattivo il prodotto
    client.put(f"/api/products/{pid}",
               json={**products[0], "active": False}, headers=admin_headers)
    r = client.post("/api/orders", json={"items": [{"product_id": pid, "quantity": 1}]})
    assert r.status_code == 400


def test_order_print_sets_printed(client):
    products = client.get("/api/products").json()
    body = {"items": [{"product_id": products[0]["id"], "quantity": 1}]}
    order = client.post("/api/orders", json=body).json()
    r = client.post(f"/api/orders/{order['id']}/print")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    # ora l'ordine risulta stampato
    assert client.get(f"/api/orders/{order['id']}").json()["printed"] is True


def test_sales_csv(client):
    products = client.get("/api/products").json()
    client.post("/api/orders",
                json={"items": [{"product_id": products[0]["id"], "quantity": 3}]})
    r = client.get("/api/reports/sales.csv")
    assert r.status_code == 200
    assert "order_id,created_at,product_name" in r.text
    assert products[0]["name"] in r.text


def test_summary(client):
    products = client.get("/api/products").json()
    client.post("/api/orders",
                json={"items": [{"product_id": products[0]["id"], "quantity": 2}]})
    r = client.get("/api/reports/summary")
    assert r.status_code == 200
    data = r.json()
    assert data["orders_count"] == 1
    assert data["total_cents"] == products[0]["price_cents"] * 2
    assert len(data["top_products"]) >= 1


def test_settings_get_hides_pin(client):
    r = client.get("/api/settings")
    assert r.status_code == 200
    assert "admin_pin" not in r.json()
    assert r.json()["association_name"] == "Associazione"


def test_settings_update_requires_pin(client, admin_headers):
    assert client.put("/api/settings",
                      json={"association_name": "X"}).status_code == 401
    r = client.put("/api/settings",
                   json={"association_name": "Pro Loco"}, headers=admin_headers)
    assert r.status_code == 200
    assert client.get("/api/settings").json()["association_name"] == "Pro Loco"


def test_reset_requires_confirm_and_pin(client, admin_headers):
    products = client.get("/api/products").json()
    client.post("/api/orders",
                json={"items": [{"product_id": products[0]["id"], "quantity": 1}]})
    # senza PIN
    assert client.post("/api/reset", json={"confirm": True}).status_code == 401
    # PIN ma senza conferma
    assert client.post("/api/reset", json={"confirm": False},
                       headers=admin_headers).status_code == 400
    # ok
    r = client.post("/api/reset", json={"confirm": True}, headers=admin_headers)
    assert r.status_code == 200
    assert client.get("/api/reports/summary").json()["orders_count"] == 0
