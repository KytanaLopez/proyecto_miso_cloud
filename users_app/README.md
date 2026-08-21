# users_app

Microservicio de gestión de usuarios (registro, actualización, autenticación por token uuid y consulta de información). Hace parte del proyecto del curso
MISW-4301 Desarrollo de Aplicaciones en la Nube (Grupo 28).

## Estructura

```
users_app/
├── Dockerfile          # Imagen del microservicio (python:3.11-slim + uvicorn)
├── main.py             # Aplicación FastAPI: modelo, validaciones y endpoints
├── test_main.py        # Pruebas unitarias (pytest, cobertura >= 70%)
├── requirements.txt    # Dependencias
└── README.md
```

## Endpoints

| Método | Ruta | Descripción |
| --- | --- | --- |
| POST | /users | Crear usuario |
| PATCH | /users/{id} | Actualizar usuario (status, dni, fullName, phoneNumber) |
| POST | /users/auth | Generar token de sesión |
| GET | /users/me | Información del usuario dueño del token |
| GET | /users/count | Cantidad de usuarios |
| GET | /users/ping | Salud del servicio (responde `pong`) |
| POST | /users/reset | Borra todos los datos |

## Variables de entorno

| Variable | Descripción | Valor por defecto |
| --- | --- | --- |
| DATABASE_URL | URL completa de conexión (tiene prioridad; usada en pruebas con SQLite) | - |
| DB_HOST | Host de PostgreSQL | - |
| DB_PORT | Puerto de PostgreSQL | 5432 |
| DB_USER | Usuario de PostgreSQL | postgres |
| DB_PASSWORD | Contraseña de PostgreSQL | postgres |
| DB_NAME | Nombre de la base de datos | users_db |

Si no se define ninguna variable, la aplicación usa un archivo SQLite local
(`users_local.db`), útil para desarrollo.

## Ejecutar localmente

```bash
cd users_app
pip install -r requirements.txt
uvicorn main:app --reload --port 3000
```

## Ejecutar las pruebas

```bash
cd users_app
pytest test_main.py --cov=main --cov-report=term-missing --cov-fail-under=70
```

## Construir la imagen Docker

```bash
docker build -t users-app:1.0.0 ./users_app
```
