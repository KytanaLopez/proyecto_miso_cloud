"""
routes_app - Microservicio de gestión de trayectos (rutas).

Expone el API REST definido en la vista funcional:
  POST   /routes         -> crear trayecto
  GET    /routes         -> listar / filtrar por ?flight={flightId}
  GET    /routes/{id}    -> consultar un trayecto
  DELETE /routes/{id}    -> eliminar un trayecto
  GET    /routes/count   -> cantidad de trayectos
  GET    /routes/ping    -> salud del servicio
  POST   /routes/reset   -> limpiar base de datos

Reglas de negocio relevantes:
  - flightId es único (repetido -> 412).
  - Fechas en el pasado o no consecutivas (fin <= inicio) -> 412 con el
    mensaje "Las fechas del trayecto no son válidas".
"""

import os
import time
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy import Column, DateTime, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# ---------------------------------------------------------------------------
# Configuración de base de datos
# ---------------------------------------------------------------------------

def build_db_url() -> str:
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    host = os.getenv("DB_HOST")
    if host:
        user = os.getenv("DB_USER", "postgres")
        password = os.getenv("DB_PASSWORD", "postgres")
        port = os.getenv("DB_PORT", "5432")
        name = os.getenv("DB_NAME", "routes_db")
        return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}"
    return "sqlite:///./routes_local.db"


DB_URL = build_db_url()
connect_args = {"check_same_thread": False} if DB_URL.startswith("sqlite") else {}
engine = create_engine(DB_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


class Route(Base):
    """Entidad trayecto según la vista de información."""

    __tablename__ = "routes"

    id = Column(String(36), primary_key=True)
    flightId = Column(String(60), unique=True, nullable=False, index=True)
    sourceAirportCode = Column(String(10), nullable=False)
    sourceCountry = Column(String(120), nullable=False)
    destinyAirportCode = Column(String(10), nullable=False)
    destinyCountry = Column(String(120), nullable=False)
    bagCost = Column(Integer, nullable=False)
    plannedStartDate = Column(DateTime, nullable=False)
    plannedEndDate = Column(DateTime, nullable=False)
    createdAt = Column(DateTime, nullable=False)
    updatedAt = Column(DateTime, nullable=False)


def init_db(retries: int = 30, wait_seconds: int = 2) -> None:
    for attempt in range(retries):
        try:
            Base.metadata.create_all(engine)
            return
        except Exception:  # pragma: no cover
            if attempt == retries - 1:
                raise
            time.sleep(wait_seconds)


init_db()

# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


def to_iso(value):
    return value.isoformat() if value else None


def parse_iso(value):
    """Convierte una cadena ISO (acepta 'Z' y zona horaria) a datetime UTC naive."""
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def is_uuid(value) -> bool:
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, AttributeError, TypeError):
        return False


def is_non_empty_str(value) -> bool:
    return isinstance(value, str) and value.strip() != ""


def route_to_dict(route: Route) -> dict:
    return {
        "id": route.id,
        "flightId": route.flightId,
        "sourceAirportCode": route.sourceAirportCode,
        "sourceCountry": route.sourceCountry,
        "destinyAirportCode": route.destinyAirportCode,
        "destinyCountry": route.destinyCountry,
        "bagCost": route.bagCost,
        "plannedStartDate": to_iso(route.plannedStartDate),
        "plannedEndDate": to_iso(route.plannedEndDate),
        "createdAt": to_iso(route.createdAt),
    }


async def read_json(request: Request):
    try:
        data = await request.json()
    except Exception:
        return None
    return data if isinstance(data, dict) else None


# ---------------------------------------------------------------------------
# Aplicación
# ---------------------------------------------------------------------------

app = FastAPI(title="routes_app")


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    return Response(status_code=400)


@app.get("/routes/ping")
def ping():
    return PlainTextResponse("pong_grupo_28")


@app.post("/routes/reset")
def reset():
    db = SessionLocal()
    try:
        db.query(Route).delete()
        db.commit()
    finally:
        db.close()
    return {"msg": "Todos los datos fueron eliminados"}


@app.get("/routes/count")
def count():
    db = SessionLocal()
    try:
        total = db.query(Route).count()
    finally:
        db.close()
    return {"count": total}


@app.post("/routes")
async def create_route(request: Request):
    data = await read_json(request)
    if data is None:
        return Response(status_code=400)

    string_fields = (
        "flightId",
        "sourceAirportCode",
        "sourceCountry",
        "destinyAirportCode",
        "destinyCountry",
    )
    for field in string_fields:
        if not is_non_empty_str(data.get(field)):
            return Response(status_code=400)

    bag_cost = data.get("bagCost")
    if isinstance(bag_cost, bool) or not isinstance(bag_cost, (int, float)):
        return Response(status_code=400)
    if isinstance(bag_cost, float):
        if not bag_cost.is_integer():
            return Response(status_code=400)
        bag_cost = int(bag_cost)

    if "plannedStartDate" not in data or "plannedEndDate" not in data:
        return Response(status_code=400)
    start = parse_iso(data.get("plannedStartDate"))
    end = parse_iso(data.get("plannedEndDate"))
    if start is None or end is None:
        return Response(status_code=400)

    # Fechas en el pasado o no consecutivas -> 412 con mensaje definido
    now = utc_now()
    if start < now or end < now or end <= start:
        return JSONResponse(
            status_code=412,
            content={"msg": "Las fechas del trayecto no son válidas"},
        )

    db = SessionLocal()
    try:
        exists = db.query(Route).filter(Route.flightId == data["flightId"]).first()
        if exists is not None:
            return Response(status_code=412)

        route = Route(
            id=str(uuid.uuid4()),
            flightId=data["flightId"],
            sourceAirportCode=data["sourceAirportCode"],
            sourceCountry=data["sourceCountry"],
            destinyAirportCode=data["destinyAirportCode"],
            destinyCountry=data["destinyCountry"],
            bagCost=bag_cost,
            plannedStartDate=start,
            plannedEndDate=end,
            createdAt=now,
            updatedAt=now,
        )
        db.add(route)
        db.commit()
        return JSONResponse(
            status_code=201,
            content={"id": route.id, "createdAt": to_iso(route.createdAt)},
        )
    finally:
        db.close()


@app.get("/routes")
def list_routes(flight: str | None = None):
    db = SessionLocal()
    try:
        query = db.query(Route)
        if flight is not None:
            query = query.filter(Route.flightId == flight)
        return [route_to_dict(route) for route in query.all()]
    finally:
        db.close()


@app.get("/routes/{route_id}")
def get_route(route_id: str):
    if not is_uuid(route_id):
        return Response(status_code=400)
    db = SessionLocal()
    try:
        route = db.query(Route).filter(Route.id == route_id).first()
        if route is None:
            return Response(status_code=404)
        return route_to_dict(route)
    finally:
        db.close()


@app.delete("/routes/{route_id}")
def delete_route(route_id: str):
    if not is_uuid(route_id):
        return Response(status_code=400)
    db = SessionLocal()
    try:
        route = db.query(Route).filter(Route.id == route_id).first()
        if route is None:
            return Response(status_code=404)
        db.delete(route)
        db.commit()
        return {"msg": "el trayecto fue eliminado"}
    finally:
        db.close()
