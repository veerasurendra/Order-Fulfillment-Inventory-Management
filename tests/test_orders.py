from decimal import Decimal
import pytest
from tests.conftest import get_auth_headers


def test_create_order_reserves_inventory(client, seed_data):
    customer_headers = get_auth_headers(seed_data["customer"])
    wh_id = seed_data["wh1"].id
    prod_id = seed_data["prod1"].id  # available 100, reserved 20

    payload = {
        "warehouse_id": wh_id,
        "items": [{"product_id": prod_id, "quantity": 10, "discount": 0.00}],
        "notes": "Deliver during business hours",
    }
    resp = client.post("/api/orders", json=payload, headers=customer_headers)
    assert resp.status_code == 201
    order = resp.json()["data"]
    assert order["status"] == "PENDING"
    assert len(order["items"]) == 1
    assert order["items"][0]["quantity"] == 10
    assert Decimal(str(order["items"][0]["unit_price"])) == Decimal("799.99")

    # Verify inventory was reserved: available was 100 -> now 90, reserved was 20 -> now 30
    admin_headers = get_auth_headers(seed_data["admin"])
    inv_resp = client.get(f"/api/inventory?product_id={prod_id}&warehouse_id={wh_id}", headers=admin_headers)
    inv = inv_resp.json()["data"][0]
    assert inv["available_quantity"] == 90
    assert inv["reserved_quantity"] == 30


def test_order_price_invariance(client, seed_data):
    customer_headers = get_auth_headers(seed_data["customer"])
    admin_headers = get_auth_headers(seed_data["admin"])
    wh_id = seed_data["wh1"].id
    prod_id = seed_data["prod1"].id

    # 1. Create order
    payload = {
        "warehouse_id": wh_id,
        "items": [{"product_id": prod_id, "quantity": 1}],
    }
    order_resp = client.post("/api/orders", json=payload, headers=customer_headers)
    order_id = order_resp.json()["data"]["id"]
    original_price = order_resp.json()["data"]["items"][0]["unit_price"]

    # 2. Admin updates product price to a higher amount
    client.put(f"/api/products/{prod_id}", json={"price": 9999.99}, headers=admin_headers)

    # 3. Retrieve order again -> item price MUST remain original
    get_resp = client.get(f"/api/orders/{order_id}", headers=customer_headers)
    assert get_resp.json()["data"]["items"][0]["unit_price"] == original_price


def test_create_order_insufficient_inventory(client, seed_data):
    customer_headers = get_auth_headers(seed_data["customer"])
    wh_id = seed_data["wh1"].id
    prod2_id = seed_data["prod2"].id  # Only 5 available

    payload = {
        "warehouse_id": wh_id,
        "items": [{"product_id": prod2_id, "quantity": 50}],
    }
    resp = client.post("/api/orders", json=payload, headers=customer_headers)
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INSUFFICIENT_INVENTORY"


def test_order_state_machine_workflow(client, seed_data):
    customer_headers = get_auth_headers(seed_data["customer"])
    agent_headers = get_auth_headers(seed_data["agent"])
    wh_id = seed_data["wh1"].id
    prod_id = seed_data["prod1"].id

    # 1. Place order (PENDING)
    order_resp = client.post(
        "/api/orders",
        json={"warehouse_id": wh_id, "items": [{"product_id": prod_id, "quantity": 2}]},
        headers=customer_headers,
    )
    order_id = order_resp.json()["data"]["id"]
    assert order_resp.json()["data"]["status"] == "PENDING"

    # 2. Payment confirmed -> CONFIRMED
    pay_resp = client.post(f"/api/orders/{order_id}/payment", json={"payment_method": "CREDIT_CARD"}, headers=customer_headers)
    assert pay_resp.status_code == 200
    assert pay_resp.json()["data"]["status"] == "CONFIRMED"

    # 3. Fulfillment starts processing -> PROCESSING
    proc_resp = client.post(f"/api/orders/{order_id}/start-processing", headers=agent_headers)
    assert proc_resp.status_code == 200
    assert proc_resp.json()["data"]["status"] == "PROCESSING"

    # 4. Pack -> PACKED
    pack_resp = client.post(f"/api/orders/{order_id}/pack", headers=agent_headers)
    assert pack_resp.status_code == 200
    assert pack_resp.json()["data"]["status"] == "PACKED"

    # 5. Ship -> SHIPPED
    ship_resp = client.post(f"/api/orders/{order_id}/ship", headers=agent_headers)
    assert ship_resp.status_code == 200
    assert ship_resp.json()["data"]["status"] == "SHIPPED"

    # 6. Deliver -> DELIVERED
    deliv_resp = client.post(f"/api/orders/{order_id}/deliver", headers=agent_headers)
    assert deliv_resp.status_code == 200
    assert deliv_resp.json()["data"]["status"] == "DELIVERED"

    # 7. Invalid transition: DELIVERED -> PROCESSING must be rejected!
    invalid_resp = client.post(f"/api/orders/{order_id}/start-processing", headers=agent_headers)
    assert invalid_resp.status_code == 400
    assert invalid_resp.json()["error"]["code"] == "INVALID_ORDER_STATUS"


def test_order_cancellation_releases_stock(client, seed_data):
    customer_headers = get_auth_headers(seed_data["customer"])
    admin_headers = get_auth_headers(seed_data["admin"])
    wh_id = seed_data["wh1"].id
    prod_id = seed_data["prod1"].id

    # Check baseline available and reserved
    inv_before = client.get(f"/api/inventory?product_id={prod_id}&warehouse_id={wh_id}", headers=admin_headers).json()["data"][0]
    avail_before = inv_before["available_quantity"]
    res_before = inv_before["reserved_quantity"]

    # Create order for 5 units
    order_resp = client.post(
        "/api/orders",
        json={"warehouse_id": wh_id, "items": [{"product_id": prod_id, "quantity": 5}]},
        headers=customer_headers,
    )
    order_id = order_resp.json()["data"]["id"]

    # Cancel order
    cancel_resp = client.post(
        f"/api/orders/{order_id}/cancel",
        json={"reason": "Customer changed mind"},
        headers=customer_headers,
    )
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["data"]["status"] == "CANCELLED"

    # Stock should be fully restored
    inv_after = client.get(f"/api/inventory?product_id={prod_id}&warehouse_id={wh_id}", headers=admin_headers).json()["data"][0]
    assert inv_after["available_quantity"] == avail_before
    assert inv_after["reserved_quantity"] == res_before


def test_order_assignment_rules(client, seed_data):
    customer_headers = get_auth_headers(seed_data["customer"])
    manager_headers = get_auth_headers(seed_data["manager"])
    wh_id = seed_data["wh1"].id
    prod_id = seed_data["prod1"].id

    order_resp = client.post(
        "/api/orders",
        json={"warehouse_id": wh_id, "items": [{"product_id": prod_id, "quantity": 1}]},
        headers=customer_headers,
    )
    order_id = order_resp.json()["data"]["id"]

    # 1. Customer cannot assign order
    cust_assign = client.post(
        f"/api/orders/{order_id}/assign",
        json={"agent_id": seed_data["agent"].id},
        headers=customer_headers,
    )
    assert cust_assign.status_code == 403

    # 2. Cannot assign to inactive agent
    inactive_assign = client.post(
        f"/api/orders/{order_id}/assign",
        json={"agent_id": seed_data["inactive_agent"].id},
        headers=manager_headers,
    )
    assert inactive_assign.status_code == 400

    # 3. Successful assignment by manager
    succ_assign = client.post(
        f"/api/orders/{order_id}/assign",
        json={"agent_id": seed_data["agent"].id, "notes": "Please expedite"},
        headers=manager_headers,
    )
    assert succ_assign.status_code == 200
    assert succ_assign.json()["data"]["assigned_agent_id"] == seed_data["agent"].id
