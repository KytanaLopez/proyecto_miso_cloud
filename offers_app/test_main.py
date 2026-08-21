"""Pruebas unitarias de offers_app (pytest + TestClient, base SQLite)."""

import os
import uuid

os.environ["DATABASE_URL"] = "sqlite:///./test_offers.db"

import pytest
from fastapi.testclient import TestClient

import main

client = TestClient(main.app)

POST_ID = str(uuid.uuid4())
USER_ID = str(uuid.uuid4())


def offer_body(**overrides):
    body = {
        "postId": POST_ID,
        "userId": USER_ID,
        "description": "paquete con documentos",
        "size": "MEDIUM",
        "fragile": True,
        "offer": 150,
    }
    body.update(overrides)
    return body


@pytest.fixture(autouse=True)
def clean_database():
    client.post("/offers/reset")
    yield


# ---------------------------- salud y utilidades ----------------------------

def test_ping():
    response = client.get("/offers/ping")
    assert response.status_code == 200
    assert response.text == "pong"


def test_reset():
    client.post("/offers", json=offer_body())
    response = client.post("/offers/reset")
    assert response.status_code == 200
    assert client.get("/offers/count").json()["count"] == 0


def test_count():
    client.post("/offers", json=offer_body())
    assert client.get("/offers/count").json()["count"] == 1


# ------------------------------ creación de ofertas --------------------------

def test_create_offer_success():
    response = client.post("/offers", json=offer_body())
    assert response.status_code == 201
    body = response.json()
    assert "id" in body and "userId" in body and "createdAt" in body


def test_create_offer_missing_fields():
    response = client.post("/offers", json={"offer": 100})
    assert response.status_code == 400


def test_create_offer_invalid_post_id():
    response = client.post("/offers", json=offer_body(postId="invalidToken"))
    assert response.status_code == 400


def test_create_offer_invalid_user_id():
    response = client.post("/offers", json=offer_body(userId="invalidToken"))
    assert response.status_code == 400


def test_create_offer_invalid_fragile():
    response = client.post("/offers", json=offer_body(fragile="si"))
    assert response.status_code == 400


def test_create_offer_invalid_offer_type():
    response = client.post("/offers", json=offer_body(offer="cien"))
    assert response.status_code == 400


def test_create_offer_invalid_size():
    response = client.post("/offers", json=offer_body(size="invalid"))
    assert response.status_code == 412


def test_create_offer_negative():
    response = client.post("/offers", json=offer_body(offer=-100))
    assert response.status_code == 412


def test_create_offer_description_too_long():
    response = client.post("/offers", json=offer_body(description="x" * 141))
    assert response.status_code == 412


# ------------------------------- listar ofertas ------------------------------

def test_list_offers_without_filters():
    offer_id = client.post("/offers", json=offer_body()).json()["id"]
    response = client.get("/offers")
    assert response.status_code == 200
    offers = response.json()
    assert len(offers) == 1
    offer = offers[0]
    assert offer["id"] == offer_id
    for field in (
        "postId",
        "description",
        "size",
        "fragile",
        "offer",
        "createdAt",
        "userId",
    ):
        assert field in offer


def test_list_offers_by_post():
    client.post("/offers", json=offer_body())
    response = client.get("/offers", params={"post": POST_ID})
    assert response.status_code == 200
    offers = response.json()
    assert len(offers) == 1
    assert offers[0]["postId"] == POST_ID


def test_list_offers_by_owner():
    client.post("/offers", json=offer_body())
    response = client.get("/offers", params={"owner": USER_ID})
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_list_offers_other_owner():
    client.post("/offers", json=offer_body())
    response = client.get(
        "/offers", params={"owner": "bf8792d2-3097-11ee-be56-0242ac120002"}
    )
    assert response.status_code == 200
    assert response.json() == []


def test_list_offers_all_filters():
    offer_id = client.post("/offers", json=offer_body()).json()["id"]
    response = client.get("/offers", params={"post": POST_ID, "owner": USER_ID})
    assert response.status_code == 200
    offers = response.json()
    assert len(offers) == 1
    assert offers[0]["id"] == offer_id


def test_list_offers_invalid_filter():
    response = client.get("/offers", params={"post": "invalidToken"})
    assert response.status_code == 400


# ------------------------------ consultar oferta -----------------------------

def test_get_offer():
    offer_id = client.post("/offers", json=offer_body()).json()["id"]
    response = client.get(f"/offers/{offer_id}")
    assert response.status_code == 200
    assert response.json()["id"] == offer_id


def test_get_offer_invalid_id():
    response = client.get("/offers/1")
    assert response.status_code == 400


def test_get_offer_not_found():
    response = client.get("/offers/bf8792d2-3097-11ee-be56-0242ac120002")
    assert response.status_code == 404


# ------------------------------ eliminar oferta ------------------------------

def test_delete_offer():
    offer_id = client.post("/offers", json=offer_body()).json()["id"]
    response = client.delete(f"/offers/{offer_id}")
    assert response.status_code == 200
    assert response.json()["msg"] == "la oferta fue eliminada"
    assert client.get("/offers/count").json()["count"] == 0


def test_delete_offer_invalid_id():
    response = client.delete("/offers/1")
    assert response.status_code == 400


def test_delete_offer_not_found():
    response = client.delete("/offers/bf8792d2-3097-11ee-be56-0242ac120002")
    assert response.status_code == 404
