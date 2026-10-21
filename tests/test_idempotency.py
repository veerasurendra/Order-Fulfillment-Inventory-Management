import uuid
import pytest
from tests.conftest import get_auth_headers


def test_idempotent_order_creation(client, seed_data):
    customer_headers = get_auth_headers(seed_data["customer"])
    admin_headers = get_auth_headers(seed_data["admin"])
    wh_id = seed_data["wh1"].id
    prod_id = seed_data["prod1"].id

    idem_key = str(uuid.uuid4())
    headers = {**customer_headers, "Idempotency-Key": idem_key}

    payload = {
        "warehouse_id": wh_id,
        "items": [{"product_id": prod_id, "quantity": 3}],
    }

    # 1. First execution
    first_resp = client.post("/api/orders", json=payload, headers=headers)
    assert first_resp.status_code == 201
    first_order = first_resp.json()["data"]

    # 2. Second execution with identical key and payload (network retry scenario)
    second_resp = client.post("/api/orders", json=payload, headers=headers)
    assert second_resp.status_code == 201
    second_order = second_resp.json()["data"]

    # Both must return the identical order number!
    assert first_order["order_number"] == second_order["order_number"]
    assert first_order["id"] == second_order["id"]

    # Verify inventory was ONLY reserved once (3 units, not 6)
    inv_resp = client.get(f"/api/inventory?product_id={prod_id}&warehouse_id={wh_id}", headers=admin_headers)
    inv = inv_resp.json()["data"][0]
    assert inv["available_quantity"] == 97  # 100 - 3 = 97


def test_idempotency_key_payload_conflict(client, seed_data):
    customer_headers = get_auth_headers(seed_data["customer"])
    wh_id = seed_data["wh1"].id
    prod_id = seed_data["prod1"].id

    idem_key = str(uuid.uuid4())
    headers = {**customer_headers, "Idempotency-Key": idem_key}

    # First request
    client.post(
        "/api/orders",
        json={"warehouse_id": wh_id, "items": [{"product_id": prod_id, "quantity": 1}]},
        headers=headers,
    )

    # Reusing same key with DIFFERENT payload -> Conflict!
    conflict_resp = client.post(
        "/api/orders",
        json={"warehouse_id": wh_id, "items": [{"product_id": prod_id, "quantity": 5}]},
        headers=headers,
    )
    assert conflict_resp.status_code == 409
    assert conflict_resp.json()["error"]["code"] == "DUPLICATE_IDEMPOTENCY_KEY"
