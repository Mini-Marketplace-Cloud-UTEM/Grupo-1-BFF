from datetime import datetime, timezone

import httpx
from fastapi import FastAPI, HTTPException, status
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.routers import auth, cart, catalog, orders, reports
from app.schemas import ErrorResponse

app = FastAPI(
    title="Marketplace BFF",
    description="Backend for Frontend - Grupo 1",
    version="1.0.0",
)

# El frontend (Vercel + localhost en desarrollo) llama directo al BFF desde
# el navegador - sin esto, el preflight OPTIONS falla y fetch() reporta
# "Failed to fetch" sin mas detalle. Restringimos a nuestros origenes: la
# lista exacta de dev local + un regex para cualquier despliegue de Vercel
# (produccion y previews de QA/Dev). Ya no usamos "*". Se usan tokens Bearer
# (no cookies), por eso allow_credentials queda en False.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.frontend_origins.split(",") if o.strip()],
    allow_origin_regex=settings.frontend_origin_regex,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    detail = exc.detail if isinstance(exc.detail, dict) else {"code": "ERROR", "message": str(exc.detail)}
    error = ErrorResponse(
        code=detail.get("code", "ERROR"),
        message=detail.get("message", "Error inesperado."),
        correlationId=request.headers.get("X-Correlation-Id"),
    )
    return JSONResponse(status_code=exc.status_code, content=jsonable_encoder(error))


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc: Exception):
    code = "UPSTREAM_TIMEOUT" if isinstance(exc, httpx.TimeoutException) else "INTERNAL_ERROR"
    error = ErrorResponse(
        code=code,
        message="El servicio dependiente no respondió a tiempo." if code == "UPSTREAM_TIMEOUT" else "Error interno.",
        correlationId=request.headers.get("X-Correlation-Id"),
    )
    return JSONResponse(status_code=status.HTTP_502_BAD_GATEWAY, content=jsonable_encoder(error))


app.include_router(auth.router, prefix="/v1")
app.include_router(catalog.router, prefix="/v1")
app.include_router(cart.router, prefix="/v1")
app.include_router(orders.router, prefix="/v1")
app.include_router(reports.router, prefix="/v1")


@app.api_route("/", methods=["GET", "HEAD"])
async def root():
    return {"message": "Marketplace BFF (Grupo 1) is running. Ver /docs para el contrato."}


@app.get("/health")
async def health():
    return {"status": "ok", "service": "g1-bff", "version": "1.0.0", "timestamp": datetime.now(timezone.utc)}
