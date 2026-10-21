import pytest
from tests.conftest import get_auth_headers


def test_admin_dashboard(client, seed_data):
    admin_headers = get_auth_headers(seed_data["admin"])
    resp = client.get("/api/dashboard/admin", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "total_orders" in data
    assert "pending_orders" in data
    assert "total_revenue" in data
    assert "low_stock_products_count" in data


def test_warehouse_manager_dashboard(client, seed_data):
    manager_headers = get_auth_headers(seed_data["manager"])
    wh1_id = seed_data["wh1"].id
    resp = client.get(f"/api/dashboard/warehouse-manager?warehouse_id={wh1_id}", headers=manager_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["warehouse_id"] == wh1_id
    assert "total_inventory_items" in data
    assert "low_stock_items" in data


def test_customer_dashboard(client, seed_data):
    customer_headers = get_auth_headers(seed_data["customer"])
    resp = client.get("/api/dashboard/customer", headers=customer_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "total_orders" in data
    assert "active_orders" in data
    assert "total_spending" in data


def test_notifications_endpoints(client, seed_data):
    customer_headers = get_auth_headers(seed_data["customer"])
    wh_id = seed_data["wh1"].id
    prod_id = seed_data["prod1"].id

    # Place order to generate notification
    client.post(
        "/api/orders",
        json={"warehouse_id": wh_id, "items": [{"product_id": prod_id, "quantity": 1}]},
        headers=customer_headers,
    )

    # 1. List notifications
    list_resp = client.get("/api/notifications", headers=customer_headers)
    assert list_resp.status_code == 200
    notifs = list_resp.json()["data"]
    assert len(notifs) >= 1
    notif_id = notifs[0]["id"]

    # 2. Mark single notification read
    mark_resp = client.patch(f"/api/notifications/{notif_id}/read", headers=customer_headers)
    assert mark_resp.status_code == 200
    assert mark_resp.json()["data"]["is_read"] is True

    # 3. Mark all read
    read_all_resp = client.patch("/api/notifications/read-all", headers=customer_headers)
    assert read_all_resp.status_code == 200
