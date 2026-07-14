import uuid
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Query

from app.config import settings
from app.dependencies import get_current_user
from app.schemas import AuthenticatedUser

# Proxy de lectura del BFF hacia el servicio de Pedidos (Grupo 5), para "Mis
# pedidos". El pedido se CREA en el checkout de G4 (POST /v1/cart/{id}/checkout),
# que orquesta G5+G8; el BFF ya no crea pedidos directo.
#   GET /v1/orders        -> GET {g5}/users/{uid}/orders  (pedidos del usuario logueado)
#   GET /v1/orders/{id}   -> GET {g5}/orders/{id}         (+ chequeo de dueno en el BFF)
#
# Seguridad: G5 corre SIN auth en el MVP, asi que el BFF es el borde de seguridad.
# El `userId` SIEMPRE sale del JWT validado (get_current_user), nunca del cliente.

router = APIRouter(prefix="/orders", tags=["orders"])


def _g5_base() -> str:
    return settings.orders_service_url.rstrip("/")


def _headers(
    authorization: Optional[str],
    correlation_id: Optional[str],
    idempotency_key: Optional[str] = None,
    with_idempotency: bool = False,
) -> dict:
    headers = {
        "X-Request-Id": str(uuid.uuid4()),
        "X-Correlation-Id": correlation_id or str(uuid.uuid4()),
        "X-Consumer": "frontend-bff",
    }
    if authorization:
        headers["Authorization"] = authorization
    if with_idempotency:
        headers["Idempotency-Key"] = idempotency_key or str(uuid.uuid4())
    return headers


def _raise_from(response: httpx.Response):
    try:
        body = response.json()
    except ValueError:
        body = {}
    code = body.get("code") or "ORDERS_ERROR"
    message = body.get("message") or (
        body.get("detail") if isinstance(body.get("detail"), str) else None
    ) or "Error en el servicio de pedidos (Grupo 5)."
    raise HTTPException(status_code=response.status_code, detail={"code": code, "message": message})


@router.get("")
async def list_orders(
    page: int = Query(1, ge=1),
    pageSize: int = Query(10, ge=1, le=50),
    user: AuthenticatedUser = Depends(get_current_user),
    authorization: Optional[str] = Header(None),
    x_correlation_id: Optional[str] = Header(None),
):
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            f"{_g5_base()}/users/{user.id}/orders",
            params={"page": page, "pageSize": pageSize},
            headers=_headers(authorization, x_correlation_id),
        )
    if response.status_code != 200:
        _raise_from(response)
    return response.json()


@router.get("/{order_id}")
async def get_order(
    order_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    authorization: Optional[str] = Header(None),
    x_correlation_id: Optional[str] = Header(None),
):
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            f"{_g5_base()}/orders/{order_id}",
            headers=_headers(authorization, x_correlation_id),
        )
    if response.status_code != 200:
        _raise_from(response)
    order = response.json()
    # G5 no valida auth: solo el dueno (o un admin) puede ver el pedido.
    if str(order.get("userId")) != str(user.id) and "admin" not in user.roles:
        raise HTTPException(
            status_code=403,
            detail={"code": "FORBIDDEN", "message": "Este pedido no te pertenece."},
        )
    return order
