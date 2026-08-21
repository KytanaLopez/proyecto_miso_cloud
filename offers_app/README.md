# offers_app

Microservicio de gestión de ofertas sobre publicaciones. Hace parte del proyecto del curso
MISW-4301 Desarrollo de Aplicaciones en la Nube (Grupo 28).

## Estructura

```
offers_app/
├── Dockerfile          # Imagen del microservicio (python:3.11-slim + uvicorn)
├── main.py             # Aplicación FastAPI: modelo, validaciones y endpoints
├── test_main.py        # Pruebas unitarias (pytest, cobertura >= 70%)
├── requirements.txt    # Dependencias
└── README.md
```

## Endpoints

| Método | Ruta | Descripción |
| --- | --- | --- |
| POST | /offers | Crear oferta |
| GET | /offers | Listar y filtrar (`post`, `owner`) |
| GET | /offers/{id} | Consultar una oferta |
| DELETE | /offers/{id} | Eliminar una oferta |
| GET | /offers/count | Cantidad de ofertas |
| GET | /offers/ping | Salud del servicio (responde `pong`) |
| POST | /offers/reset | Borra todos los datos |

## Variables de entorno

| Variable | Descripción | Valor por defecto |
| --- | --- | --- |
| DATABASE_URL | URL completa de conexión (tiene prioridad; usada en pruebas con SQLite) | - |
| DB_HOST | Host de PostgreSQL | - |
| DB_PORT | Puerto de PostgreSQL | 5432 |
| DB_USER | Usuario de PostgreSQL | postgres |
| DB_PASSWORD | Contraseña de PostgreSQL | postgres |
| DB_NAME | Nombre de la base de datos | offers_db |

Si no se define ninguna variable, la aplicación usa un archivo SQLite local
(`offers_local.db`), útil para desarrollo.

## Ejecutar localmente

```bash
cd offers_app
pip install -r requirements.txt
uvicorn main:app --reload --port 3003
```

## Ejecutar las pruebas

```bash
cd offers_app
pytest test_main.py --cov=main --cov-report=term-missing --cov-fail-under=70
```

## Construir la imagen Docker

```bash
docker build -t offers-app:1.0.0 ./offers_app
```
