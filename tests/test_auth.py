import pytest
from tests.conftest import get_auth_headers


def test_register_success(client):
    payload = {
        "email": "newuser@example.com",
        "username": "newuser",
        "password": "Password123!",
        "full_name": "New User",
    }
    resp = client.post("/api/auth/register", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["email"] == "newuser@example.com"
    assert data["data"]["role"] == "CUSTOMER"


def test_register_duplicate_email(client, seed_data):
    payload = {
        "email": seed_data["customer"].email,
        "username": "anotheruser",
        "password": "Password123!",
        "full_name": "Another User",
    }
    resp = client.post("/api/auth/register", json=payload)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "CONFLICT"


def test_login_success(client, seed_data):
    payload = {
        "username_or_email": seed_data["customer"].username,
        "password": "customerpass123",
    }
    resp = client.post("/api/auth/login", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "access_token" in data["data"]
    assert "refresh_token" in data["data"]


def test_login_invalid_password(client, seed_data):
    payload = {
        "username_or_email": seed_data["customer"].username,
        "password": "wrongpassword",
    }
    resp = client.post("/api/auth/login", json=payload)
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"


def test_login_inactive_user(client, seed_data):
    payload = {
        "username_or_email": seed_data["inactive_user"].username,
        "password": "inactive123",
    }
    resp = client.post("/api/auth/login", json=payload)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "USER_INACTIVE"


def test_refresh_token_rotation(client, seed_data):
    # 1. Login to obtain tokens
    login_resp = client.post(
        "/api/auth/login",
        json={"username_or_email": seed_data["customer"].email, "password": "customerpass123"},
    )
    tokens = login_resp.json()["data"]
    initial_refresh = tokens["refresh_token"]

    # 2. Refresh
    refresh_resp = client.post("/api/auth/refresh", json={"refresh_token": initial_refresh})
    assert refresh_resp.status_code == 200
    new_tokens = refresh_resp.json()["data"]
    assert new_tokens["access_token"] != tokens["access_token"]
    assert new_tokens["refresh_token"] != initial_refresh

    # 3. Old refresh token is now revoked -> attempting to reuse must fail!
    reuse_resp = client.post("/api/auth/refresh", json={"refresh_token": initial_refresh})
    assert reuse_resp.status_code == 401
    assert "revoked" in reuse_resp.json()["error"]["message"].lower()


def test_logout(client, seed_data):
    login_resp = client.post(
        "/api/auth/login",
        json={"username_or_email": seed_data["customer"].email, "password": "customerpass123"},
    )
    refresh_token = login_resp.json()["data"]["refresh_token"]

    logout_resp = client.post("/api/auth/logout", json={"refresh_token": refresh_token})
    assert logout_resp.status_code == 200

    # Refresh after logout should fail
    refresh_resp = client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_resp.status_code == 401


def test_get_me(client, seed_data):
    headers = get_auth_headers(seed_data["customer"])
    resp = client.get("/api/auth/me", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["email"] == seed_data["customer"].email


def test_change_password(client, seed_data):
    headers = get_auth_headers(seed_data["customer"])
    payload = {
        "old_password": "customerpass123",
        "new_password": "NewStrongPassword456!",
    }
    resp = client.post("/api/auth/change-password", json=payload, headers=headers)
    assert resp.status_code == 200

    # Verify old password fails
    fail_login = client.post(
        "/api/auth/login",
        json={"username_or_email": seed_data["customer"].email, "password": "customerpass123"},
    )
    assert fail_login.status_code == 401

    # Verify new password succeeds
    succ_login = client.post(
        "/api/auth/login",
        json={"username_or_email": seed_data["customer"].email, "password": "NewStrongPassword456!"},
    )
    assert succ_login.status_code == 200
