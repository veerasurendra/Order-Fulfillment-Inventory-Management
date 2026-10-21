import pytest
from tests.conftest import get_auth_headers


def test_admin_create_warehouse(client, seed_data):
    admin_headers = get_auth_headers(seed_data["admin"])
    payload = {
        "name": "East Coast Mega Hub",
        "location": "Newark, NJ",
        "capacity": 50000,
        "status": "ACTIVE",
    }
    resp = client.post("/api/warehouses", json=payload, headers=admin_headers)
    assert resp.status_code == 201
    assert resp.json()["data"]["name"] == "East Coast Mega Hub"


def test_customer_cannot_create_warehouse(client, seed_data):
    customer_headers = get_auth_headers(seed_data["customer"])
    payload = {
        "name": "Unauthorized Warehouse",
        "location": "Miami, FL",
        "capacity": 1000,
        "status": "ACTIVE",
    }
    resp = client.post("/api/warehouses", json=payload, headers=customer_headers)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


def test_manager_access_authorized_warehouse(client, seed_data):
    # Manager is assigned to wh1
    manager_headers = get_auth_headers(seed_data["manager"])
    wh1_id = seed_data["wh1"].id
    resp = client.get(f"/api/warehouses/{wh1_id}", headers=manager_headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == wh1_id


def test_manager_access_unauthorized_warehouse(client, seed_data):
    # Manager is NOT assigned to wh2
    manager_headers = get_auth_headers(seed_data["manager"])
    wh2_id = seed_data["wh2"].id
    resp = client.get(f"/api/warehouses/{wh2_id}", headers=manager_headers)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "WAREHOUSE_ACCESS_DENIED"


def test_manager_update_authorized_warehouse(client, seed_data):
    manager_headers = get_auth_headers(seed_data["manager"])
    wh1_id = seed_data["wh1"].id
    resp = client.put(
        f"/api/warehouses/{wh1_id}",
        json={"capacity": 25000},
        headers=manager_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["capacity"] == 25000


def test_assign_and_unassign_user_to_warehouse(client, seed_data):
    admin_headers = get_auth_headers(seed_data["admin"])
    wh2_id = seed_data["wh2"].id
    manager_id = seed_data["manager"].id

    # Assign manager to wh2
    assign_resp = client.post(
        f"/api/warehouses/{wh2_id}/users",
        json={"user_id": manager_id},
        headers=admin_headers,
    )
    assert assign_resp.status_code == 201

    # Now manager can view wh2
    manager_headers = get_auth_headers(seed_data["manager"])
    get_resp = client.get(f"/api/warehouses/{wh2_id}", headers=manager_headers)
    assert get_resp.status_code == 200

    # Unassign manager from wh2
    del_resp = client.delete(f"/api/warehouses/{wh2_id}/users/{manager_id}", headers=admin_headers)
    assert del_resp.status_code == 200

    # Now manager cannot view wh2
    denied_resp = client.get(f"/api/warehouses/{wh2_id}", headers=manager_headers)
    assert denied_resp.status_code == 403
