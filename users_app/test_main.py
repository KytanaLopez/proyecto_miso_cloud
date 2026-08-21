"""Pruebas unitarias de users_app (pytest + TestClient, base SQLite)."""

import os
from datetime import timedelta

os.environ["DATABASE_URL"] = "sqlite:///./test_users.db"

import pytest
from fastapi.testclient import TestClient

import main
from main import SessionLocal, User, utc_now

client = TestClient(main.app)

USER_BODY = {
    "username": "calletana",
    "password": "SuperSecreta123",
    "email": "calletana@uniandes.edu.co",
    "dni": "123456789",
    "fullName": "calletana perez",
    "phoneNumber": "3001234567",
}


@pytest.fixture(autouse=True)
def clean_database():
    client.post("/users/reset")
    yield


def create_user(body=None):
    return client.post("/users", json=body or USER_BODY)


def auth_user():
    return client.post(
        "/users/auth",
        json={"username": USER_BODY["username"], "password": USER_BODY["password"]},
    )


# ---------------------------- salud y utilidades ----------------------------

def test_ping():
    response = client.get("/users/ping")
    assert response.status_code == 200
    assert response.text == "pong"


def test_reset():
    create_user()
    response = client.post("/users/reset")
    assert response.status_code == 200
    assert response.json()["msg"] == "Todos los datos fueron eliminados"
    assert client.get("/users/count").json()["count"] == 0


def test_count():
    create_user()
    response = client.get("/users/count")
    assert response.status_code == 200
    assert response.json()["count"] == 1


# ---------------------------- creación de usuarios ---------------------------

def test_create_user_success():
    response = create_user()
    assert response.status_code == 201
    body = response.json()
    assert "id" in body and "createdAt" in body


def test_create_user_duplicated():
    create_user()
    response = create_user()
    assert response.status_code == 412


def test_create_user_duplicated_email():
    create_user()
    other = dict(USER_BODY, username="otrousuario")
    response = create_user(other)
    assert response.status_code == 412


def test_create_user_missing_fields():
    response = create_user({"fullName": "solo nombre"})
    assert response.status_code == 400


def test_create_user_invalid_email():
    response = create_user(dict(USER_BODY, email="correo_invalido"))
    assert response.status_code == 400


def test_create_user_invalid_body():
    response = client.post(
        "/users", content=b"no-json", headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 400


# --------------------------- actualización de usuarios -----------------------

def test_update_user_success():
    user_id = create_user().json()["id"]
    response = client.patch(
        f"/users/{user_id}",
        json={"status": "VERIFICADO", "fullName": "nuevo nombre"},
    )
    assert response.status_code == 200
    assert response.json()["msg"] == "el usuario ha sido actualizado"


def test_update_user_without_fields():
    user_id = create_user().json()["id"]
    response = client.patch(f"/users/{user_id}", json={})
    assert response.status_code == 400


def test_update_user_invalid_fields():
    user_id = create_user().json()["id"]
    response = client.patch(f"/users/{user_id}", json={"email": "otro@mail.com"})
    assert response.status_code == 400


def test_update_user_invalid_status():
    user_id = create_user().json()["id"]
    response = client.patch(f"/users/{user_id}", json={"status": "INVALIDO"})
    assert response.status_code == 400


def test_update_user_not_found():
    create_user()
    response = client.patch(
        "/users/bf8792d2-3097-11ee-be56-0242ac120002",
        json={"status": "VERIFICADO"},
    )
    assert response.status_code == 404


# ------------------------------ generación de token --------------------------

def test_auth_success():
    create_user()
    response = auth_user()
    assert response.status_code == 200
    body = response.json()
    assert "id" in body and "token" in body and "expireAt" in body


def test_auth_wrong_password():
    create_user()
    response = client.post(
        "/users/auth",
        json={"username": USER_BODY["username"], "password": "incorrecta"},
    )
    assert response.status_code == 404


def test_auth_user_not_found():
    response = client.post("/users/auth", json={"username": "fake", "password": "fake"})
    assert response.status_code == 404


def test_auth_missing_fields():
    response = client.post("/users/auth", json={"username": USER_BODY["username"]})
    assert response.status_code == 400


# ------------------------------- consultar /me -------------------------------

def test_me_success():
    create_user()
    token = auth_user().json()["token"]
    response = client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["username"] == USER_BODY["username"]
    assert body["email"] == USER_BODY["email"]
    assert body["status"] == "POR_VERIFICAR"


def test_me_without_token():
    response = client.get("/users/me")
    assert response.status_code == 403


def test_me_invalid_token():
    create_user()
    token = auth_user().json()["token"]
    response = client.get(
        "/users/me", headers={"Authorization": f"Bearer {token}fake"}
    )
    assert response.status_code == 401


def test_me_expired_token():
    create_user()
    token = auth_user().json()["token"]
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.token == token).first()
        user.expireAt = utc_now() - timedelta(hours=2)
        db.commit()
    finally:
        db.close()
    response = client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
