import pytest
from tests.conftest import get_auth_headers


def test_create_product_admin(client, seed_data):
    admin_headers = get_auth_headers(seed_data["admin"])
    payload = {
        "sku": "SKU-MONITOR-03",
        "name": "4K Gaming Monitor",
        "description": "32-inch 144Hz monitor",
        "price": 499.99,
        "cost_price": 300.00,
        "status": "ACTIVE",
    }
    resp = client.post("/api/products", json=payload, headers=admin_headers)
    assert resp.status_code == 201
    assert resp.json()["data"]["sku"] == "SKU-MONITOR-03"


def test_create_product_duplicate_sku(client, seed_data):
    admin_headers = get_auth_headers(seed_data["admin"])
    payload = {
        "sku": seed_data["prod1"].sku,  # Duplicate
        "name": "Another Phone",
        "price": 699.99,
    }
    resp = client.post("/api/products", json=payload, headers=admin_headers)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "CONFLICT"


def test_customer_cannot_create_product(client, seed_data):
    customer_headers = get_auth_headers(seed_data["customer"])
    payload = {
        "sku": "SKU-TEST-99",
        "name": "Test Product",
        "price": 10.00,
    }
    resp = client.post("/api/products", json=payload, headers=customer_headers)
    assert resp.status_code == 403


def test_list_products_with_filter(client, seed_data):
    resp = client.get("/api/products?search=Laptop")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) >= 1
    assert any("Laptop" in p["name"] for p in data)


def test_activate_and_deactivate_product(client, seed_data):
    admin_headers = get_auth_headers(seed_data["admin"])
    prod_id = seed_data["prod1"].id

    # Deactivate
    deact_resp = client.patch(f"/api/products/{prod_id}/deactivate", headers=admin_headers)
    assert deact_resp.status_code == 200
    assert deact_resp.json()["data"]["status"] == "INACTIVE"

    # Activate
    act_resp = client.patch(f"/api/products/{prod_id}/activate", headers=admin_headers)
    assert act_resp.status_code == 200
    assert act_resp.json()["data"]["status"] == "ACTIVE"


def test_order_inactive_product_rejected(client, seed_data):
    customer_headers = get_auth_headers(seed_data["customer"])
    wh_id = seed_data["wh1"].id
    inactive_prod_id = seed_data["prod_inactive"].id

    order_payload = {
        "warehouse_id": wh_id,
        "items": [{"product_id": inactive_prod_id, "quantity": 1}],
    }
    resp = client.post("/api/orders", json=order_payload, headers=customer_headers)
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "PRODUCT_INACTIVE"
