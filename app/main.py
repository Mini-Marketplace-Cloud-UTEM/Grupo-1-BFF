from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from app.routers import auth, cart, catalog, orders
from app.schemas import ErrorResponse

app = FastAPI(
    title="Marketplace BFF",
    description="Backend for Frontend - Grupo 1",
    version="1.0.0",
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


app.include_router(auth.router, prefix="/v1")
app.include_router(catalog.router, prefix="/v1")
app.include_router(cart.router, prefix="/v1")
app.include_router(orders.router, prefix="/v1")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "g1-bff", "version": "1.0.0", "timestamp": datetime.now(timezone.utc)}
