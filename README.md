# Grupo 1 — BFF (Backend for Frontend)

API que consume el frontend React del marketplace. Traduce y orquesta las
llamadas hacia los servicios de los grupos 2-8. El frontend **solo** habla
con este servicio — nunca directo con los demás.

Contrato completo (fuente de verdad): [`marketplace-contracts/services/group-1-bff/openapi.yaml`](https://github.com/Mini-Marketplace-Cloud-UTEM/marketplace-contracts/blob/main/services/group-1-bff/openapi.yaml).

## Stack

- Python 3.10 + FastAPI + Docker — mismo stack que usa Grupo 6 (el único
  grupo con un servicio real desplegado hasta ahora), y lo que pide la
  lista de tecnologías del curso (Render + Python).
- `httpx` para llamar a los servicios de los demás grupos (sin DB propia:
  el BFF no persiste nada, solo orquesta).

## Estado actual

- ✅ `/health` y manejo de errores estándar (`{code, message, details?, correlationId?}`).
- ✅ `/v1/auth/*` implementado contra Grupo 2 (única URL real en producción hoy, ver `registro-de-servicios.md`), con traducción snake_case → camelCase.
- ⚠️ `/v1/products*`, `/v1/categories`, `/v1/cart*`, `/v1/orders*` son **stubs** (501) — los servicios de Grupo 3/4/5 todavía no tienen URL real ni mock confirmado. Ver el TODO en cada router (`app/routers/`).
- ⚠️ Validación de JWT centralizada vía `POST /auth/validate` de Grupo 2 (`app/dependencies.py`), implementada pero todavía no se usa en ningún endpoint (los stubs no la requieren aún).

## Configuración y ejecución local

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1   # Windows
pip install -r requirements.txt
cp .env.example .env         # ajustar URLs según registro-de-servicios.md
uvicorn app.main:app --reload
```

Swagger: `http://127.0.0.1:8000/docs`

## Docker

```bash
docker build -t grupo1-bff .
docker run -d -p 8000:8000 --env-file .env grupo1-bff
```

## Próximos pasos

1. Implementar `/v1/products*` y `/v1/categories` contra el mock Prism de Grupo 3 (`marketplace-contracts/data-dictionary/contratos-mock.md`).
2. Implementar `/v1/cart*` contra Grupo 4.
3. Implementar `POST /v1/orders` llamando a `POST /v1/checkout` de Grupo 4 (no reimplementar la orquestación — ver `decisiones-ejecutivas-2026-06-19.md` #1).
4. Desplegar en Render y actualizar la fila propia en `marketplace-contracts/registro-de-servicios.md`.
