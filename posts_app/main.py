"""
posts_app - Microservicio de gestión de publicaciones.

Expone el API REST definido en la vista funcional:
  POST   /posts         -> crear publicación
  GET    /posts         -> listar / filtrar ?expire={true|false}&route={id}&owner={id}
  GET    /posts/{id}    -> consultar una publicación
  DELETE /posts/{id}    -> eliminar una publicación
  GET    /posts/count   -> cantidad de publicaciones
  GET    /posts/ping    -> salud del servicio
  POST   /posts/reset   -> limpiar base de datos

Reglas de negocio relevantes:
  - routeId y userId deben tener formato uuid (si no -> 400).
  - expireAt debe ser una fecha futura; de lo contrario -> 412 con el
    mensaje "La fecha expiración no es válida".
"""

import os
import time
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy import Column, DateTime, String, create_engine
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
        name = os.getenv("DB_NAME", "posts_db")
        return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}"
    return "sqlite:///./posts_local.db"


DB_URL = build_db_url()
connect_args = {"check_same_thread": False} if DB_URL.startswith("sqlite") else {}
engine = create_engine(DB_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


class Post(Base):
    """Entidad publicación según la vista de información."""

    __tablename__ = "posts"

    id = Column(String(36), primary_key=True)
    routeId = Column(String(36), nullable=False, index=True)
    userId = Column(String(36), nullable=False, index=True)
    expireAt = Column(DateTime, nullable=False)
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


def parse_iso(value):
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


def post_to_dict(post: Post) -> dict:
    return {
        "id": post.id,
        "routeId": post.routeId,
        "userId": post.userId,
        "expireAt": to_iso(post.expireAt),
        "createdAt": to_iso(post.createdAt),
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

app = FastAPI(title="posts_app")


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    return Response(status_code=400)


@app.get("/posts/ping")
def ping():
    return PlainTextResponse("pong")


@app.post("/posts/reset")
def reset():
    db = SessionLocal()
    try:
        db.query(Post).delete()
        db.commit()
    finally:
        db.close()
    return {"msg": "Todos los datos fueron eliminados"}


@app.get("/posts/count")
def count():
    db = SessionLocal()
    try:
        total = db.query(Post).count()
    finally:
        db.close()
    return {"count": total}


@app.post("/posts")
async def create_post(request: Request):
    data = await read_json(request)
    if data is None:
        return Response(status_code=400)

    route_id = data.get("routeId")
    user_id = data.get("userId")
    expire_at_raw = data.get("expireAt")

    # Campos obligatorios y formato esperado -> si no, 400
    if route_id is None or user_id is None or expire_at_raw is None:
        return Response(status_code=400)
    if not is_uuid(route_id) or not is_uuid(user_id):
        return Response(status_code=400)
    expire_at = parse_iso(expire_at_raw)
    if expire_at is None:
        return Response(status_code=400)

    # La fecha de expiración debe ser futura -> si no, 412
    if expire_at <= utc_now():
        return JSONResponse(
            status_code=412,
            content={"msg": "La fecha expiración no es válida"},
        )

    db = SessionLocal()
    try:
        post = Post(
            id=str(uuid.uuid4()),
            routeId=str(route_id),
            userId=str(user_id),
            expireAt=expire_at,
            createdAt=utc_now(),
        )
        db.add(post)
        db.commit()
        return JSONResponse(
            status_code=201,
            content={
                "id": post.id,
                "userId": post.userId,
                "createdAt": to_iso(post.createdAt),
            },
        )
    finally:
        db.close()


@app.get("/posts")
def list_posts(expire: str | None = None, route: str | None = None, owner: str | None = None):
    # Validación de formato de los filtros -> 400
    if expire is not None and expire.lower() not in ("true", "false"):
        return Response(status_code=400)
    if route is not None and not is_uuid(route):
        return Response(status_code=400)
    if owner is not None and not is_uuid(owner):
        return Response(status_code=400)

    db = SessionLocal()
    try:
        query = db.query(Post)
        if route is not None:
            query = query.filter(Post.routeId == route)
        if owner is not None:
            query = query.filter(Post.userId == owner)
        if expire is not None:
            now = utc_now()
            if expire.lower() == "true":
                query = query.filter(Post.expireAt < now)
            else:
                query = query.filter(Post.expireAt >= now)
        return [post_to_dict(post) for post in query.all()]
    finally:
        db.close()


@app.get("/posts/{post_id}")
def get_post(post_id: str):
    if not is_uuid(post_id):
        return Response(status_code=400)
    db = SessionLocal()
    try:
        post = db.query(Post).filter(Post.id == post_id).first()
        if post is None:
            return Response(status_code=404)
        return post_to_dict(post)
    finally:
        db.close()


@app.delete("/posts/{post_id}")
def delete_post(post_id: str):
    if not is_uuid(post_id):
        return Response(status_code=400)
    db = SessionLocal()
    try:
        post = db.query(Post).filter(Post.id == post_id).first()
        if post is None:
            return Response(status_code=404)
        db.delete(post)
        db.commit()
        return {"msg": "la publicación fue eliminada"}
    finally:
        db.close()
