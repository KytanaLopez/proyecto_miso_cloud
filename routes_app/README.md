# routes_app

Microservicio de gestión de trayectos (rutas de vuelo). Hace parte del proyecto del curso
MISW-4301 Desarrollo de Aplicaciones en la Nube (Grupo 28).

## Estructura

```
routes_app/
├── Dockerfile          # Imagen del microservicio (python:3.11-slim + uvicorn)
├── main.py             # Aplicación FastAPI: modelo, validaciones y endpoints
├── test_main.py        # Pruebas unitarias (pytest, cobertura >= 70%)
├── requirements.txt    # Dependencias
└── README.md
```

## Endpoints

| Método | Ruta | Descripción |
| --- | --- | --- |
| POST | /routes | Crear trayecto |
| GET | /routes | Listar y filtrar (`flight`) |
| GET | /routes/{id} | Consultar un trayecto |
| DELETE | /routes/{id} | Eliminar un trayecto |
| GET | /routes/count | Cantidad de trayectos |
| GET | /routes/ping | Salud del servicio (responde `pong_grupo_28`) |
| POST | /routes/reset | Borra todos los datos |

## Variables de entorno

| Variable | Descripción | Valor por defecto |
| --- | --- | --- |
| DATABASE_URL | URL completa de conexión (tiene prioridad; usada en pruebas con SQLite) | - |
| DB_HOST | Host de PostgreSQL | - |
| DB_PORT | Puerto de PostgreSQL | 5432 |
| DB_USER | Usuario de PostgreSQL | postgres |
| DB_PASSWORD | Contraseña de PostgreSQL | postgres |
| DB_NAME | Nombre de la base de datos | routes_db |

Si no se define ninguna variable, la aplicación usa un archivo SQLite local
(`routes_local.db`), útil para desarrollo.

## Ejecutar localmente

```bash
cd routes_app
pip install -r requirements.txt
uvicorn main:app --reload --port 3002
```

## Ejecutar las pruebas

```bash
cd routes_app
pytest test_main.py --cov=main --cov-report=term-missing --cov-fail-under=70
```

## Construir la imagen Docker

```bash
docker build -t routes-app:1.0.0 ./routes_app
```
