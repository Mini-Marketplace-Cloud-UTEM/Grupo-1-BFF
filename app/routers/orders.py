import uuid
from typing import List, Optional

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field

from app.config import settings
from app.dependencies import get_current_user
from app.schemas import AuthenticatedUser

# Proxy del BFF hacia el nuevo servicio de Pedidos (Grupo 5), tras la toma de
# responsabilidad por la desercion de G5. Contrato G5 (sin prefijo /v1):
#   POST /orders                     crear pedido (Idempotency-Key obligatorio)
#   GET  /orders/{orderId}           obtener un pedido
#   GET  /users/{userId}/orders      listar pedidos de un usuario (paginado)
#
# Mapeo del BFF:
#   POST /v1/orders        -> POST {g5}/orders            (BRIDGE, ver nota abajo)
#   GET  /v1/orders        -> GET  {g5}/users/{uid}/orders  (pedidos del usuario logueado)
#   GET  /v1/orders/{id}   -> GET  {g5}/orders/{id}        (+ chequeo de dueno en el BFF)
#
# Seguridad: G5 corre SIN auth en el MVP, asi que el BFF es el borde de seguridad.
# El `userId` SIEMPRE sale del JWT validado (get_current_user), nunca del body.
#
# NOTA BRIDGE (temporal): por la decision ejecutiva 2026-06-19, el checkout lo
# orquesta G4 (que deberia llamar a G5). Mientras G4 arregla su checkout y apunta
# su URL de pedidos al nuevo G5, el BFF crea el pedido directo en G5 para no
# bloquear el flujo del front. Cuando G4 quede cableado, el POST vuelve a pasar
# por G4 (cart /complete) y este endpoint puede quitarse o quedar de respaldo.

router = APIRouter(prefix="/orders", tags=["orders"])


class OrderItemIn(BaseModel):
    productId: str
    name: str
    quantity: int = Field(gt=0)
    unitPrice: int
    subtotal: int


class ShippingAddressIn(BaseModel):
    street: str
    city: str
    region: str
    country: str = "Chile"
    postalCode: Optional[str] = None


class CreateOrderBody(BaseModel):
    items: List[OrderItemIn] = Field(min_length=1)
    shippingAddress: Optional[ShippingAddressIn] = None
    notes: Optional[str] = None


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


@router.post("")
async def create_order(
    body: CreateOrderBody,
    user: AuthenticatedUser = Depends(get_current_user),
    authorization: Optional[str] = Header(None),
    x_correlation_id: Optional[str] = Header(None),
    idempotency_key: Optional[str] = Header(None),
):
    payload = {
        "userId": user.id,
        "items": [item.model_dump() for item in body.items],
        "shippingAddress": body.shippingAddress.model_dump() if body.shippingAddress else None,
        "notes": body.notes,
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            f"{_g5_base()}/orders",
            json=payload,
            headers=_headers(authorization, x_correlation_id, idempotency_key, with_idempotency=True),
        )
    if response.status_code not in (200, 201):
        _raise_from(response)
    return response.json()


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
