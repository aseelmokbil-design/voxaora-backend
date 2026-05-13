"""Integration tests for VOXAORA Auth API"""
import pytest


@pytest.mark.asyncio
async def test_register_new_user(client):
    response = await client.post("/api/v1/auth/register", json={
        "phone": "+966511111001",
        "full_name": "أحمد تجريبي",
        "password": "Test@12345",
        "preferred_language": "ar",
    })
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert data["user"]["phone"] == "+966511111001"


@pytest.mark.asyncio
async def test_register_duplicate_phone(client):
    payload = {
        "phone": "+966511111002",
        "full_name": "مستخدم مكرر",
        "password": "Test@12345",
    }
    await client.post("/api/v1/auth/register", json=payload)
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_login_success(client):
    phone = "+966511111003"
    await client.post("/api/v1/auth/register", json={
        "phone": phone,
        "full_name": "Login Test",
        "password": "Test@12345",
    })
    response = await client.post("/api/v1/auth/login", json={
        "phone": phone,
        "password": "Test@12345",
    })
    assert response.status_code == 200
    assert "access_token" in response.json()


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    phone = "+966511111004"
    await client.post("/api/v1/auth/register", json={
        "phone": phone,
        "full_name": "Wrong Pass",
        "password": "Test@12345",
    })
    response = await client.post("/api/v1/auth/login", json={
        "phone": phone,
        "password": "WrongPassword",
    })
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_profile_authenticated(client):
    phone = "+966511111005"
    reg = await client.post("/api/v1/auth/register", json={
        "phone": phone,
        "full_name": "Profile Test",
        "password": "Test@12345",
    })
    token = reg.json()["access_token"]
    response = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["phone"] == phone


@pytest.mark.asyncio
async def test_health_endpoint(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
