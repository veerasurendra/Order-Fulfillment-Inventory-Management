import pytest
from tests.conftest import get_auth_headers


def test_inventory_adjust_increase(client, seed_data):
    manager_headers = get_auth_headers(seed_data["manager"])
    wh_id = seed_data["wh1"].id
    prod_id = seed_data["prod1"].id

    payload = {
        "product_id": prod_id,
        "warehouse_id": wh_id,
        "adjustment_type": "INCREASE",
        "quantity": 25,
        "reason": "Restock from shipment",
    }
    resp = client.post("/api/inventory/adjust", json=payload, headers=manager_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["previous_quantity"] == 100
    assert data["new_quantity"] == 125
    assert data["adjustment_amount"] == 25


def test_inventory_adjust_decrease_insufficient(client, seed_data):
    manager_headers = get_auth_headers(seed_data["manager"])
    wh_id = seed_data["wh1"].id
    prod_id = seed_data["prod1"].id

    payload = {
        "product_id": prod_id,
        "warehouse_id": wh_id,
        "adjustment_type": "DECREASE",
        "quantity": 9999,  # Exceeds available 100
        "reason": "Correction",
    }
    resp = client.post("/api/inventory/adjust", json=payload, headers=manager_headers)
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INSUFFICIENT_INVENTORY"


def test_inventory_adjust_damage(client, seed_data):
    manager_headers = get_auth_headers(seed_data["manager"])
    wh_id = seed_data["wh1"].id
    prod_id = seed_data["prod1"].id

    payload = {
        "product_id": prod_id,
        "warehouse_id": wh_id,
        "adjustment_type": "DAMAGE",
        "quantity": 5,
        "reason": "Water damage inspection",
    }
    resp = client.post("/api/inventory/adjust", json=payload, headers=manager_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["inventory"]["damaged_quantity"] == 5
    assert data["new_quantity"] == 95


def test_inventory_transfer_success(client, seed_data):
    admin_headers = get_auth_headers(seed_data["admin"])
    wh1_id = seed_data["wh1"].id
    wh2_id = seed_data["wh2"].id
    prod_id = seed_data["prod1"].id

    payload = {
        "source_warehouse_id": wh1_id,
        "destination_warehouse_id": wh2_id,
        "product_id": prod_id,
        "quantity": 20,
        "reason": "Rebalance regional stock",
    }
    resp = client.post("/api/inventory/transfer", json=payload, headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["source_available_quantity"] == 80  # 100 - 20
    assert data["destination_available_quantity"] == 70  # 50 + 20


def test_inventory_transfer_insufficient_stock(client, seed_data):
    admin_headers = get_auth_headers(seed_data["admin"])
    wh1_id = seed_data["wh1"].id
    wh2_id = seed_data["wh2"].id
    prod2_id = seed_data["prod2"].id  # available = 5

    payload = {
        "source_warehouse_id": wh1_id,
        "destination_warehouse_id": wh2_id,
        "product_id": prod2_id,
        "quantity": 50,  # Only 5 available
    }
    resp = client.post("/api/inventory/transfer", json=payload, headers=admin_headers)
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INSUFFICIENT_INVENTORY"


def test_get_low_stock_items(client, seed_data):
    admin_headers = get_auth_headers(seed_data["admin"])
    resp = client.get("/api/inventory/low-stock", headers=admin_headers)
    assert resp.status_code == 200
    items = resp.json()["data"]
    assert len(items) >= 1
    # prod2 has available 5 <= reorder_level 10
    assert any(i["product_sku"] == seed_data["prod2"].sku for i in items)


def test_immutable_inventory_transactions_created(client, seed_data):
    admin_headers = get_auth_headers(seed_data["admin"])
    # Adjust stock to trigger transaction
    client.post(
        "/api/inventory/adjust",
        json={
            "product_id": seed_data["prod1"].id,
            "warehouse_id": seed_data["wh1"].id,
            "adjustment_type": "INCREASE",
            "quantity": 10,
            "reason": "Audit count test",
        },
        headers=admin_headers,
    )

    tx_resp = client.get(
        f"/api/inventory/transactions?product_id={seed_data['prod1'].id}",
        headers=admin_headers,
    )
    assert tx_resp.status_code == 200
    txs = tx_resp.json()["data"]
    assert len(txs) >= 1
    assert any(tx["transaction_type"] == "ADJUSTMENT" for tx in txs)
