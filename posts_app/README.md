# posts_app

Microservicio de gestión de publicaciones asociadas a trayectos. Hace parte del proyecto del curso
MISW-4301 Desarrollo de Aplicaciones en la Nube (Grupo 28).

## Estructura

```
posts_app/
├── Dockerfile          # Imagen del microservicio (python:3.11-slim + uvicorn)
├── main.py             # Aplicación FastAPI: modelo, validaciones y endpoints
├── test_main.py        # Pruebas unitarias (pytest, cobertura >= 70%)
├── requirements.txt    # Dependencias
└── README.md
```

## Endpoints

| Método | Ruta | Descripción |
| --- | --- | --- |
| POST | /posts | Crear publicación |
| GET | /posts | Listar y filtrar (`expire`, `route`, `owner`) |
| GET | /posts/{id} | Consultar una publicación |
| DELETE | /posts/{id} | Eliminar una publicación |
| GET | /posts/count | Cantidad de publicaciones |
| GET | /posts/ping | Salud del servicio (responde `pong`) |
| POST | /posts/reset | Borra todos los datos |

## Variables de entorno

| Variable | Descripción | Valor por defecto |
| --- | --- | --- |
| DATABASE_URL | URL completa de conexión (tiene prioridad; usada en pruebas con SQLite) | - |
| DB_HOST | Host de PostgreSQL | - |
| DB_PORT | Puerto de PostgreSQL | 5432 |
| DB_USER | Usuario de PostgreSQL | postgres |
| DB_PASSWORD | Contraseña de PostgreSQL | postgres |
| DB_NAME | Nombre de la base de datos | posts_db |

Si no se define ninguna variable, la aplicación usa un archivo SQLite local
(`posts_local.db`), útil para desarrollo.

## Ejecutar localmente

```bash
cd posts_app
pip install -r requirements.txt
uvicorn main:app --reload --port 3001
```

## Ejecutar las pruebas

```bash
cd posts_app
pytest test_main.py --cov=main --cov-report=term-missing --cov-fail-under=70
```

## Construir la imagen Docker

```bash
docker build -t posts-app:1.0.0 ./posts_app
```
