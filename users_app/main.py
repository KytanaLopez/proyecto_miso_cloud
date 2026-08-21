"""
users_app - Microservicio de gestión de usuarios.

Expone el API REST definido en la vista funcional:
  POST   /users        -> crear usuario
  PATCH  /users/{id}   -> actualizar usuario
  POST   /users/auth   -> generar token de sesión (uuid aleatorio, NO JWT)
  GET    /users/me     -> información del usuario dueño del token
  GET    /users/count  -> cantidad de usuarios
  GET    /users/ping   -> salud del servicio
  POST   /users/reset  -> limpiar base de datos

La conexión a base de datos se resuelve por variables de entorno:
  - DATABASE_URL (si existe, se usa tal cual; útil para pruebas con SQLite)
  - DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME (PostgreSQL en k8s)
  - Si no hay ninguna, se usa un archivo SQLite local (desarrollo rápido).
"""

import hashlib
import os
import time
import uuid
from datetime import datetime, timedelta, timezone

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
        name = os.getenv("DB_NAME", "users_db")
        return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}"
    return "sqlite:///./users_local.db"


DB_URL = build_db_url()
connect_args = {"check_same_thread": False} if DB_URL.startswith("sqlite") else {}
engine = create_engine(DB_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

VALID_STATUSES = ("POR_VERIFICAR", "NO_VERIFICADO", "VERIFICADO")


class User(Base):
    """Entidad usuario según la vista de información."""

    __tablename__ = "users"

    id = Column(String(36), primary_key=True)
    username = Column(String(120), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    phoneNumber = Column(String(60), nullable=True)
    dni = Column(String(60), nullable=True)
    fullName = Column(String(255), nullable=True)
    password = Column(String(128), nullable=False)  # hash sha256
    salt = Column(String(64), nullable=False)
    token = Column(String(36), nullable=True, index=True)
    status = Column(String(20), nullable=False, default="POR_VERIFICAR")
    expireAt = Column(DateTime, nullable=True)
    createdAt = Column(DateTime, nullable=False)
    updatedAt = Column(DateTime, nullable=False)


def init_db(retries: int = 30, wait_seconds: int = 2) -> None:
    """Crea las tablas reintentando mientras la base de datos arranca."""
    for attempt in range(retries):
        try:
            Base.metadata.create_all(engine)
            return
        except Exception:  # pragma: no cover - solo ocurre si la BD no responde
            if attempt == retries - 1:
                raise
            time.sleep(wait_seconds)


init_db()

# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def utc_now() -> datetime:
    """Fecha y hora actual en UTC (naive, según restricción del curso)."""
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


def to_iso(value):
    return value.isoformat() if value else None


def hash_password(password: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}{password}".encode("utf-8")).hexdigest()


def is_non_empty_str(value) -> bool:
    return isinstance(value, str) and value.strip() != ""


async def read_json(request: Request):
    """Lee el cuerpo JSON; retorna None si no es un objeto JSON válido."""
    try:
        data = await request.json()
    except Exception:
        return None
    return data if isinstance(data, dict) else None


# ---------------------------------------------------------------------------
# Aplicación
# ---------------------------------------------------------------------------

app = FastAPI(title="users_app")


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    """El API define 400 (no 422) para solicitudes mal formadas."""
    return Response(status_code=400)


@app.get("/users/ping")
def ping():
    return PlainTextResponse("pong")


@app.post("/users/reset")
def reset():
    db = SessionLocal()
    try:
        db.query(User).delete()
        db.commit()
    finally:
        db.close()
    return {"msg": "Todos los datos fueron eliminados"}


@app.get("/users/count")
def count():
    db = SessionLocal()
    try:
        total = db.query(User).count()
    finally:
        db.close()
    return {"count": total}


@app.get("/users/me")
def me(request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return Response(status_code=403)

    token = auth_header[7:] if auth_header.lower().startswith("bearer ") else auth_header
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.token == token).first()
        if user is None or user.expireAt is None or user.expireAt < utc_now():
            return Response(status_code=401)
        return {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "fullName": user.fullName,
            "dni": user.dni,
            "phoneNumber": user.phoneNumber,
            "status": user.status,
        }
    finally:
        db.close()


@app.post("/users")
async def create_user(request: Request):
    data = await read_json(request)
    if data is None:
        return Response(status_code=400)

    username = data.get("username")
    password = data.get("password")
    email = data.get("email")

    # Campos obligatorios presentes y con el formato esperado -> si no, 400
    if not (is_non_empty_str(username) and is_non_empty_str(password) and is_non_empty_str(email)):
        return Response(status_code=400)
    if "@" not in email or " " in email:
        return Response(status_code=400)

    # Campos opcionales: si vienen, deben ser cadenas
    optional = {}
    for field in ("dni", "fullName", "phoneNumber"):
        value = data.get(field)
        if value is not None and not isinstance(value, str):
            return Response(status_code=400)
        optional[field] = value

    db = SessionLocal()
    try:
        exists = (
            db.query(User)
            .filter((User.username == username) | (User.email == email))
            .first()
        )
        if exists is not None:
            return Response(status_code=412)

        now = utc_now()
        salt = uuid.uuid4().hex
        user = User(
            id=str(uuid.uuid4()),
            username=username,
            email=email,
            password=hash_password(password, salt),
            salt=salt,
            dni=optional["dni"],
            fullName=optional["fullName"],
            phoneNumber=optional["phoneNumber"],
            status="POR_VERIFICAR",
            createdAt=now,
            updatedAt=now,
        )
        db.add(user)
        db.commit()
        return JSONResponse(
            status_code=201,
            content={"id": user.id, "createdAt": to_iso(user.createdAt)},
        )
    finally:
        db.close()


@app.patch("/users/{user_id}")
async def update_user(user_id: str, request: Request):
    data = await read_json(request)
    if data is None:
        return Response(status_code=400)

    # Debe venir al menos uno de los campos actualizables
    updatable = ("status", "dni", "fullName", "phoneNumber")
    fields = {k: data[k] for k in updatable if k in data}
    if not fields:
        return Response(status_code=400)

    for key, value in fields.items():
        if not isinstance(value, str):
            return Response(status_code=400)
    if "status" in fields and fields["status"] not in VALID_STATUSES:
        return Response(status_code=400)

    # id inválido o inexistente -> el usuario no existe
    try:
        uuid.UUID(user_id)
    except (ValueError, AttributeError, TypeError):
        return Response(status_code=404)

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if user is None:
            return Response(status_code=404)
        for key, value in fields.items():
            setattr(user, key, value)
        user.updatedAt = utc_now()
        db.commit()
        return {"msg": "el usuario ha sido actualizado"}
    finally:
        db.close()


@app.post("/users/auth")
async def auth(request: Request):
    data = await read_json(request)
    if data is None:
        return Response(status_code=400)

    username = data.get("username")
    password = data.get("password")
    if not (is_non_empty_str(username) and is_non_empty_str(password)):
        return Response(status_code=400)

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if user is None or user.password != hash_password(password, user.salt):
            return Response(status_code=404)

        user.token = str(uuid.uuid4())
        user.expireAt = utc_now() + timedelta(hours=1)
        user.updatedAt = utc_now()
        db.commit()
        return {
            "id": user.id,
            "token": user.token,
            "expireAt": to_iso(user.expireAt),
        }
    finally:
        db.close()
