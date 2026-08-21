"""
offers_app - Microservicio de gestión de ofertas.

Expone el API REST definido en la vista funcional:
  POST   /offers         -> crear oferta
  GET    /offers         -> listar / filtrar ?post={postId}&owner={userId}
  GET    /offers/{id}    -> consultar una oferta
  DELETE /offers/{id}    -> eliminar una oferta
  GET    /offers/count   -> cantidad de ofertas
  GET    /offers/ping    -> salud del servicio
  POST   /offers/reset   -> limpiar base de datos

Reglas de negocio relevantes:
  - postId y userId deben tener formato uuid (si no -> 400).
  - size debe ser LARGE, MEDIUM o SMALL (si no -> 412).
  - offer debe ser un número no negativo (negativo -> 412).
"""

import os
import time
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy import Boolean, Column, DateTime, Float, String, create_engine
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
        name = os.getenv("DB_NAME", "offers_db")
        return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}"
    return "sqlite:///./offers_local.db"


DB_URL = build_db_url()
connect_args = {"check_same_thread": False} if DB_URL.startswith("sqlite") else {}
engine = create_engine(DB_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

VALID_SIZES = ("LARGE", "MEDIUM", "SMALL")
MAX_DESCRIPTION_LENGTH = 140


class Offer(Base):
    """Entidad oferta según la vista de información."""

    __tablename__ = "offers"

    id = Column(String(36), primary_key=True)
    postId = Column(String(36), nullable=False, index=True)
    userId = Column(String(36), nullable=False, index=True)
    description = Column(String(MAX_DESCRIPTION_LENGTH), nullable=False)
    size = Column(String(10), nullable=False)
    fragile = Column(Boolean, nullable=False)
    offer = Column(Float, nullable=False)
    createdAt = Column(DateTime, nullable=False)


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


def is_uuid(value) -> bool:
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, AttributeError, TypeError):
        return False


def offer_to_dict(offer: Offer) -> dict:
    return {
        "id": offer.id,
        "postId": offer.postId,
        "description": offer.description,
        "size": offer.size,
        "fragile": offer.fragile,
        "offer": offer.offer,
        "createdAt": to_iso(offer.createdAt),
        "userId": offer.userId,
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

app = FastAPI(title="offers_app")


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    return Response(status_code=400)


@app.get("/offers/ping")
def ping():
    return PlainTextResponse("pong")


@app.post("/offers/reset")
def reset():
    db = SessionLocal()
    try:
        db.query(Offer).delete()
        db.commit()
    finally:
        db.close()
    return {"msg": "Todos los datos fueron eliminados"}


@app.get("/offers/count")
def count():
    db = SessionLocal()
    try:
        total = db.query(Offer).count()
    finally:
        db.close()
    return {"count": total}


@app.post("/offers")
async def create_offer(request: Request):
    data = await read_json(request)
    if data is None:
        return Response(status_code=400)

    required = ("postId", "userId", "description", "size", "fragile", "offer")
    for field in required:
        if field not in data or data[field] is None:
            return Response(status_code=400)

    post_id = data["postId"]
    user_id = data["userId"]
    description = data["description"]
    size = data["size"]
    fragile = data["fragile"]
    amount = data["offer"]

    # Formato esperado -> si no, 400
    if not is_uuid(post_id) or not is_uuid(user_id):
        return Response(status_code=400)
    if not isinstance(description, str) or not isinstance(size, str):
        return Response(status_code=400)
    if not isinstance(fragile, bool):
        return Response(status_code=400)
    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        return Response(status_code=400)

    # Valores fuera de lo esperado -> 412
    if size not in VALID_SIZES:
        return Response(status_code=412)
    if amount < 0:
        return Response(status_code=412)
    if len(description) > MAX_DESCRIPTION_LENGTH:
        return Response(status_code=412)

    db = SessionLocal()
    try:
        offer = Offer(
            id=str(uuid.uuid4()),
            postId=str(post_id),
            userId=str(user_id),
            description=description,
            size=size,
            fragile=fragile,
            offer=float(amount),
            createdAt=utc_now(),
        )
        db.add(offer)
        db.commit()
        return JSONResponse(
            status_code=201,
            content={
                "id": offer.id,
                "userId": offer.userId,
                "createdAt": to_iso(offer.createdAt),
            },
        )
    finally:
        db.close()


@app.get("/offers")
def list_offers(post: str | None = None, owner: str | None = None):
    # Validación de formato de los filtros -> 400
    if post is not None and not is_uuid(post):
        return Response(status_code=400)
    if owner is not None and not is_uuid(owner):
        return Response(status_code=400)

    db = SessionLocal()
    try:
        query = db.query(Offer)
        if post is not None:
            query = query.filter(Offer.postId == post)
        if owner is not None:
            query = query.filter(Offer.userId == owner)
        return [offer_to_dict(offer) for offer in query.all()]
    finally:
        db.close()


@app.get("/offers/{offer_id}")
def get_offer(offer_id: str):
    if not is_uuid(offer_id):
        return Response(status_code=400)
    db = SessionLocal()
    try:
        offer = db.query(Offer).filter(Offer.id == offer_id).first()
        if offer is None:
            return Response(status_code=404)
        return offer_to_dict(offer)
    finally:
        db.close()


@app.delete("/offers/{offer_id}")
def delete_offer(offer_id: str):
    if not is_uuid(offer_id):
        return Response(status_code=400)
    db = SessionLocal()
    try:
        offer = db.query(Offer).filter(Offer.id == offer_id).first()
        if offer is None:
            return Response(status_code=404)
        db.delete(offer)
        db.commit()
        return {"msg": "la oferta fue eliminada"}
    finally:
        db.close()
