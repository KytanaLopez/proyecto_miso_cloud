"""Pruebas unitarias de posts_app (pytest + TestClient, base SQLite)."""

import os
import uuid
from datetime import timedelta

os.environ["DATABASE_URL"] = "sqlite:///./test_posts.db"

import pytest
from fastapi.testclient import TestClient

import main
from main import utc_now

client = TestClient(main.app)

ROUTE_ID = str(uuid.uuid4())
USER_ID = str(uuid.uuid4())


def post_body(**overrides):
    body = {
        "routeId": ROUTE_ID,
        "userId": USER_ID,
        "expireAt": (utc_now() + timedelta(days=7)).isoformat(),
    }
    body.update(overrides)
    return body


@pytest.fixture(autouse=True)
def clean_database():
    client.post("/posts/reset")
    yield


# ---------------------------- salud y utilidades ----------------------------

def test_ping():
    response = client.get("/posts/ping")
    assert response.status_code == 200
    assert response.text == "pong"


def test_reset():
    client.post("/posts", json=post_body())
    response = client.post("/posts/reset")
    assert response.status_code == 200
    assert client.get("/posts/count").json()["count"] == 0


def test_count():
    client.post("/posts", json=post_body())
    assert client.get("/posts/count").json()["count"] == 1


# --------------------------- creación de publicaciones -----------------------

def test_create_post_success():
    response = client.post("/posts", json=post_body())
    assert response.status_code == 201
    body = response.json()
    assert "id" in body and "userId" in body and "createdAt" in body


def test_create_post_missing_fields():
    response = client.post("/posts", json={"expireAt": post_body()["expireAt"]})
    assert response.status_code == 400


def test_create_post_invalid_user_id():
    response = client.post("/posts", json=post_body(userId="invalidId"))
    assert response.status_code == 400


def test_create_post_invalid_route_id():
    response = client.post("/posts", json=post_body(routeId="invalidId"))
    assert response.status_code == 400


def test_create_post_invalid_expire_format():
    response = client.post("/posts", json=post_body(expireAt="no-es-fecha"))
    assert response.status_code == 400


def test_create_post_expired_date():
    response = client.post(
        "/posts", json=post_body(expireAt="2022-08-01T21:20:53.214Z")
    )
    assert response.status_code == 412
    assert response.json()["msg"] == "La fecha expiración no es válida"


# ---------------------------- listar publicaciones ---------------------------

def test_list_posts_without_filters():
    post_id = client.post("/posts", json=post_body()).json()["id"]
    response = client.get("/posts")
    assert response.status_code == 200
    posts = response.json()
    assert len(posts) == 1
    post = posts[0]
    assert post["id"] == post_id
    for field in ("routeId", "userId", "expireAt", "createdAt"):
        assert field in post


def test_list_posts_not_expired():
    post_id = client.post("/posts", json=post_body()).json()["id"]
    response = client.get("/posts", params={"expire": "false"})
    assert response.status_code == 200
    posts = response.json()
    assert len(posts) == 1
    assert posts[0]["id"] == post_id


def test_list_posts_invalid_expire():
    response = client.get("/posts", params={"expire": "invalid"})
    assert response.status_code == 400


def test_list_posts_by_route():
    client.post("/posts", json=post_body())
    response = client.get("/posts", params={"route": ROUTE_ID})
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_list_posts_by_owner():
    client.post("/posts", json=post_body())
    response = client.get("/posts", params={"owner": USER_ID})
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_list_posts_other_owner():
    client.post("/posts", json=post_body())
    response = client.get(
        "/posts", params={"owner": "bf8792d2-3097-11ee-be56-0242ac120002"}
    )
    assert response.status_code == 200
    assert response.json() == []


def test_list_posts_invalid_owner_format():
    response = client.get("/posts", params={"owner": "invalidId"})
    assert response.status_code == 400


def test_list_posts_all_filters():
    post_id = client.post("/posts", json=post_body()).json()["id"]
    response = client.get(
        "/posts",
        params={"expire": "false", "route": ROUTE_ID, "owner": USER_ID},
    )
    assert response.status_code == 200
    posts = response.json()
    assert len(posts) == 1
    assert posts[0]["id"] == post_id


# --------------------------- consultar publicación ---------------------------

def test_get_post():
    post_id = client.post("/posts", json=post_body()).json()["id"]
    response = client.get(f"/posts/{post_id}")
    assert response.status_code == 200
    assert response.json()["id"] == post_id


def test_get_post_invalid_id():
    response = client.get("/posts/1")
    assert response.status_code == 400


def test_get_post_not_found():
    response = client.get("/posts/bf8792d2-3097-11ee-be56-0242ac120002")
    assert response.status_code == 404


# ---------------------------- eliminar publicación ---------------------------

def test_delete_post():
    post_id = client.post("/posts", json=post_body()).json()["id"]
    response = client.delete(f"/posts/{post_id}")
    assert response.status_code == 200
    assert response.json()["msg"] == "la publicación fue eliminada"
    assert client.get("/posts/count").json()["count"] == 0


def test_delete_post_invalid_id():
    response = client.delete("/posts/1")
    assert response.status_code == 400


def test_delete_post_not_found():
    response = client.delete("/posts/bf8792d2-3097-11ee-be56-0242ac120002")
    assert response.status_code == 404
