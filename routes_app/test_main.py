"""Pruebas unitarias de routes_app (pytest + TestClient, base SQLite)."""

import os
from datetime import timedelta

os.environ["DATABASE_URL"] = "sqlite:///./test_routes.db"

import pytest
from fastapi.testclient import TestClient

import main
from main import utc_now

client = TestClient(main.app)


def route_body(**overrides):
    start = utc_now() + timedelta(days=2)
    end = utc_now() + timedelta(days=10)
    body = {
        "flightId": "AA001",
        "sourceAirportCode": "BOG",
        "sourceCountry": "Colombia",
        "destinyAirportCode": "LGW",
        "destinyCountry": "Inglaterra",
        "bagCost": 100,
        "plannedStartDate": start.isoformat(),
        "plannedEndDate": end.isoformat(),
    }
    body.update(overrides)
    return body


@pytest.fixture(autouse=True)
def clean_database():
    client.post("/routes/reset")
    yield


# ---------------------------- salud y utilidades ----------------------------

def test_ping():
    response = client.get("/routes/ping")
    assert response.status_code == 200
    assert response.text == "pong_grupo_28"


def test_reset():
    client.post("/routes", json=route_body())
    response = client.post("/routes/reset")
    assert response.status_code == 200
    assert client.get("/routes/count").json()["count"] == 0


def test_count():
    client.post("/routes", json=route_body())
    assert client.get("/routes/count").json()["count"] == 1


# ---------------------------- creación de trayectos --------------------------

def test_create_route_success():
    response = client.post("/routes", json=route_body())
    assert response.status_code == 201
    body = response.json()
    assert "id" in body and "createdAt" in body


def test_create_route_start_date_in_past():
    response = client.post(
        "/routes",
        json=route_body(plannedStartDate="2022-08-01T21:20:53.214Z"),
    )
    assert response.status_code == 412
    assert response.json()["msg"] == "Las fechas del trayecto no son válidas"


def test_create_route_end_date_in_past():
    response = client.post(
        "/routes",
        json=route_body(plannedEndDate="2022-08-01T21:20:53.214Z"),
    )
    assert response.status_code == 412
    assert response.json()["msg"] == "Las fechas del trayecto no son válidas"


def test_create_route_dates_not_consecutive():
    start = utc_now() + timedelta(days=10)
    end = utc_now() + timedelta(days=2)
    response = client.post(
        "/routes",
        json=route_body(
            plannedStartDate=start.isoformat(), plannedEndDate=end.isoformat()
        ),
    )
    assert response.status_code == 412
    assert response.json()["msg"] == "Las fechas del trayecto no son válidas"


def test_create_route_duplicated_flight_id():
    client.post("/routes", json=route_body())
    response = client.post("/routes", json=route_body())
    assert response.status_code == 412


def test_create_route_missing_fields():
    response = client.post("/routes", json={"bagCost": 100})
    assert response.status_code == 400


def test_create_route_invalid_bag_cost():
    response = client.post("/routes", json=route_body(bagCost="cien"))
    assert response.status_code == 400


def test_create_route_invalid_date_format():
    response = client.post(
        "/routes", json=route_body(plannedStartDate="no-es-fecha")
    )
    assert response.status_code == 400


# ------------------------------ listar trayectos -----------------------------

def test_list_routes():
    client.post("/routes", json=route_body())
    response = client.get("/routes")
    assert response.status_code == 200
    routes = response.json()
    assert len(routes) == 1
    route = routes[0]
    for field in (
        "id",
        "flightId",
        "sourceAirportCode",
        "sourceCountry",
        "destinyAirportCode",
        "destinyCountry",
        "bagCost",
        "plannedStartDate",
        "plannedEndDate",
        "createdAt",
    ):
        assert field in route


def test_list_routes_filter_by_flight():
    client.post("/routes", json=route_body())
    client.post("/routes", json=route_body(flightId="BB002"))
    response = client.get("/routes", params={"flight": "AA001"})
    assert response.status_code == 200
    routes = response.json()
    assert len(routes) == 1
    assert routes[0]["flightId"] == "AA001"


def test_list_routes_filter_by_flight_not_found():
    client.post("/routes", json=route_body())
    response = client.get("/routes", params={"flight": "AA001fake"})
    assert response.status_code == 200
    assert response.json() == []


# ----------------------------- consultar trayecto ----------------------------

def test_get_route():
    route_id = client.post("/routes", json=route_body()).json()["id"]
    response = client.get(f"/routes/{route_id}")
    assert response.status_code == 200
    assert response.json()["id"] == route_id


def test_get_route_invalid_id():
    response = client.get("/routes/1")
    assert response.status_code == 400


def test_get_route_not_found():
    response = client.get("/routes/bf8792d2-3097-11ee-be56-0242ac120002")
    assert response.status_code == 404


# ------------------------------ eliminar trayecto ----------------------------

def test_delete_route():
    route_id = client.post("/routes", json=route_body()).json()["id"]
    response = client.delete(f"/routes/{route_id}")
    assert response.status_code == 200
    assert response.json()["msg"] == "el trayecto fue eliminado"
    assert client.get("/routes/count").json()["count"] == 0


def test_delete_route_invalid_id():
    response = client.delete("/routes/1")
    assert response.status_code == 400


def test_delete_route_not_found():
    response = client.delete("/routes/bf8792d2-3097-11ee-be56-0242ac120002")
    assert response.status_code == 404
