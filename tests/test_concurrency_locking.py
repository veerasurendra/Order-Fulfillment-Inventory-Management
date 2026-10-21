import concurrent.futures
import pytest
from tests.conftest import get_auth_headers


def test_concurrent_inventory_reservations(client, seed_data):
    """
    Simulate multiple simultaneous orders competing for limited stock.
    Stock available: 5 units.
    5 concurrent requests each asking for 2 units (Total 10 units demanded).
    Only 2 orders can succeed (2 * 2 = 4 units reserved, 1 remaining).
    Remaining 3 orders must fail with INSUFFICIENT_INVENTORY.
    Inventory must NEVER become negative.
    """
    wh_id = seed_data["wh1"].id
    prod2_id = seed_data["prod2"].id  # available = 5
    headers = get_auth_headers(seed_data["customer"])

    def place_competing_order():
        payload = {
            "warehouse_id": wh_id,
            "items": [{"product_id": prod2_id, "quantity": 2}],
        }
        return client.post("/api/orders", json=payload, headers=headers)

    num_threads = 5
    responses = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(place_competing_order) for _ in range(num_threads)]
        for f in concurrent.futures.as_completed(futures):
            responses.append(f.result())

    success_count = sum(1 for r in responses if r.status_code == 201)
    failure_count = sum(1 for r in responses if r.status_code == 400 and r.json().get("error", {}).get("code") == "INSUFFICIENT_INVENTORY")

    # With 5 units available and each order demanding 2: exactly 2 orders can succeed!
    assert success_count == 2
    assert failure_count == 3

    # Check inventory balance in database
    admin_headers = get_auth_headers(seed_data["admin"])
    inv_resp = client.get(f"/api/inventory?product_id={prod2_id}&warehouse_id={wh_id}", headers=admin_headers)
    inv = inv_resp.json()["data"][0]

    assert inv["available_quantity"] == 1  # 5 - (2*2) = 1
    assert inv["reserved_quantity"] == 4   # 2*2 = 4
    assert inv["available_quantity"] >= 0  # Strict non-negative guarantee!
