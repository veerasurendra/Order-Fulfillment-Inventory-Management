import pytest
from tests.conftest import get_auth_headers


def test_return_lifecycle_and_restock(client, seed_data):
    customer_headers = get_auth_headers(seed_data["customer"])
    agent_headers = get_auth_headers(seed_data["agent"])
    manager_headers = get_auth_headers(seed_data["manager"])
    wh_id = seed_data["wh1"].id
    prod_id = seed_data["prod1"].id

    # 1. Place order and advance through fulfillment to DELIVERED
    order_resp = client.post(
        "/api/orders",
        json={"warehouse_id": wh_id, "items": [{"product_id": prod_id, "quantity": 2}]},
        headers=customer_headers,
    )
    order_id = order_resp.json()["data"]["id"]

    client.post(f"/api/orders/{order_id}/payment", json={"payment_method": "CREDIT_CARD"}, headers=customer_headers)
    client.post(f"/api/orders/{order_id}/start-processing", headers=agent_headers)
    client.post(f"/api/orders/{order_id}/pack", headers=agent_headers)
    client.post(f"/api/orders/{order_id}/ship", headers=agent_headers)
    client.post(f"/api/orders/{order_id}/deliver", headers=agent_headers)

    # 2. Customer creates return request
    ret_payload = {
        "order_id": order_id,
        "reason": "Product arrived with slight cosmetic blemish",
        "items": [{"product_id": prod_id, "quantity": 1, "condition": "GOOD"}],
    }
    ret_resp = client.post("/api/returns", json=ret_payload, headers=customer_headers)
    assert ret_resp.status_code == 201
    ret = ret_resp.json()["data"]
    ret_id = ret["id"]
    assert ret["status"] == "REQUESTED"

    # 3. Manager approves return
    appr_resp = client.patch(
        f"/api/returns/{ret_id}/status",
        json={"status": "APPROVED", "admin_notes": "Return authorized"},
        headers=manager_headers,
    )
    assert appr_resp.status_code == 200
    assert appr_resp.json()["data"]["status"] == "APPROVED"

    # 4. Warehouse receives return -> items are restocked
    admin_headers = get_auth_headers(seed_data["admin"])
    inv_before = client.get(f"/api/inventory?product_id={prod_id}&warehouse_id={wh_id}", headers=admin_headers).json()["data"][0]["available_quantity"]

    recv_resp = client.patch(
        f"/api/returns/{ret_id}/status",
        json={"status": "RECEIVED", "admin_notes": "Item verified in original packaging"},
        headers=manager_headers,
    )
    assert recv_resp.status_code == 200
    assert recv_resp.json()["data"]["status"] == "RECEIVED"

    # Verify inventory was incremented by returned quantity (+1)
    inv_after = client.get(f"/api/inventory?product_id={prod_id}&warehouse_id={wh_id}", headers=admin_headers).json()["data"][0]["available_quantity"]
    assert inv_after == inv_before + 1


def test_return_on_pending_order_rejected(client, seed_data):
    customer_headers = get_auth_headers(seed_data["customer"])
    wh_id = seed_data["wh1"].id
    prod_id = seed_data["prod1"].id

    order_resp = client.post(
        "/api/orders",
        json={"warehouse_id": wh_id, "items": [{"product_id": prod_id, "quantity": 1}]},
        headers=customer_headers,
    )
    order_id = order_resp.json()["data"]["id"]

    # Order is PENDING, not DELIVERED
    ret_payload = {
        "order_id": order_id,
        "reason": "Cannot return undelivered order",
        "items": [{"product_id": prod_id, "quantity": 1, "condition": "GOOD"}],
    }
    ret_resp = client.post("/api/returns", json=ret_payload, headers=customer_headers)
    assert ret_resp.status_code == 400
