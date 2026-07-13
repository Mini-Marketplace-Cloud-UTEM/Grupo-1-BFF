import uuid
from typing import Optional

import httpx
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.config import settings

# Proxy real del BFF hacia Grupo 4 (Carro/Checkout/Inventario).
# Contrato real y en vivo verificado 2026-07-04 (G4 v1.2.0):
#   POST   /v1/cart
#   GET    /v1/cart/{cart_id}
#   POST   /v1/cart/{cart_id}/items      body: {productId, quantity}
#   PUT    /v1/cart/{cart_id}/items/{item_id}   body: {quantity}
#   DELETE /v1/cart/{cart_id}/items/{item_id}
#
# G4 ya devuelve montos en integer y usa `subtotal` (minuscula), igual que
# nuestro estandar. Las unicas diferencias de nombres que normalizamos:
#   cartId       -> id
#   totalAmount  -> totalPrice
#   (agregamos currency=CLP y totalItems, que G4 no entrega)
#
# Seguridad: reenviamos el header Authorization tal cual llega (passthrough).
# No lo validamos aun contra G2 porque su servicio esta en pausa; cuando
# vuelva, se agrega Depends(get_current_user) y se valida antes de proxear.

router = APIRouter(prefix="/cart", tags=["cart"])


class AddItemBody(BaseModel):
    productId: str
    quantity: int = 1


class UpdateItemBody(BaseModel):
    quantity: int


class CheckoutShippingAddress(BaseModel):
    street: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None
    country: Optional[str] = None
    postalCode: Optional[str] = None


class CheckoutBody(BaseModel):
    # G4 (v2) exige la direccion para pasarsela a G5 al crear el pedido.
    shippingAddress: Optional[CheckoutShippingAddress] = None
    notes: Optional[str] = None


def _g4_base() -> str:
    return settings.cart_service_url.rstrip("/")


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
    # G4 puede devolver {code, message} o el {detail} por defecto de FastAPI.
    code = body.get("code") or "CART_ERROR"
    message = body.get("message") or (
        body.get("detail") if isinstance(body.get("detail"), str) else None
    ) or "Error en el servicio de carrito (Grupo 4)."
    raise HTTPException(status_code=response.status_code, detail={"code": code, "message": message})


def _normalize_item(i: dict) -> dict:
    return {
        "itemId": i.get("itemId"),
        "productId": i.get("productId"),
        "name": i.get("name"),
        "unitPrice": i.get("unitPrice"),
        "quantity": i.get("quantity"),
        "subtotal": i.get("subtotal"),
    }


def _normalize_cart(c: dict) -> dict:
    items = c.get("items") or []
    return {
        "id": c.get("cartId"),
        "userId": c.get("userId"),
        "status": c.get("status"),
        "items": [_normalize_item(i) for i in items],
        "totalItems": sum(i.get("quantity", 0) for i in items),
        "totalPrice": c.get("totalAmount"),
        "currency": "CLP",
    }


def _looks_like_cart(body) -> bool:
    # Las transiciones de estado de G4 (reserva/activate) devuelven el carrito;
    # complete devuelve el pedido. Solo normalizamos cuando es realmente un carrito.
    return isinstance(body, dict) and ("cartId" in body or "items" in body)


@router.post("")
async def create_cart(
    authorization: Optional[str] = Header(None),
    x_correlation_id: Optional[str] = Header(None),
):
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            f"{_g4_base()}/v1/cart", headers=_headers(authorization, x_correlation_id)
        )
    if response.status_code not in (200, 201):
        _raise_from(response)
    return _normalize_cart(response.json())


@router.get("/{cart_id}")
async def get_cart(
    cart_id: str,
    authorization: Optional[str] = Header(None),
    x_correlation_id: Optional[str] = Header(None),
):
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            f"{_g4_base()}/v1/cart/{cart_id}", headers=_headers(authorization, x_correlation_id)
        )
    if response.status_code != 200:
        _raise_from(response)
    return _normalize_cart(response.json())


@router.post("/{cart_id}/items")
async def add_item(
    cart_id: str,
    body: AddItemBody,
    authorization: Optional[str] = Header(None),
    x_correlation_id: Optional[str] = Header(None),
    idempotency_key: Optional[str] = Header(None),
):
    # Solo mandamos productId + quantity: G4 consulta precio/stock a G3, el
    # front nunca envia precio (evita manipulacion desde el navegador).
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            f"{_g4_base()}/v1/cart/{cart_id}/items",
            json={"productId": body.productId, "quantity": body.quantity},
            headers=_headers(authorization, x_correlation_id, idempotency_key, with_idempotency=True),
        )
    if response.status_code not in (200, 201):
        _raise_from(response)
    return _normalize_cart(response.json())


@router.put("/{cart_id}/items/{item_id}")
async def update_item(
    cart_id: str,
    item_id: str,
    body: UpdateItemBody,
    authorization: Optional[str] = Header(None),
    x_correlation_id: Optional[str] = Header(None),
):
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.put(
            f"{_g4_base()}/v1/cart/{cart_id}/items/{item_id}",
            json={"quantity": body.quantity},
            headers=_headers(authorization, x_correlation_id),
        )
    if response.status_code != 200:
        _raise_from(response)
    return _normalize_cart(response.json())


@router.delete("/{cart_id}/items/{item_id}")
async def remove_item(
    cart_id: str,
    item_id: str,
    authorization: Optional[str] = Header(None),
    x_correlation_id: Optional[str] = Header(None),
):
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.delete(
            f"{_g4_base()}/v1/cart/{cart_id}/items/{item_id}",
            headers=_headers(authorization, x_correlation_id),
        )
    if response.status_code not in (200, 204):
        _raise_from(response)
    if response.status_code == 204 or not response.content:
        return {"status": "OK"}
    return _normalize_cart(response.json())


# ── Checkout real orquestado por G4 (v2, 2026-07-12) ──
# G4 crea el pedido en G5 (con la direccion) e inicia el pago en G8, y devuelve
# {status:"PENDING", paymentUrl}. El front redirige a paymentUrl (MercadoPago) y,
# al cancelar, llama a cancel_checkout para liberar el stock.


@router.post("/{cart_id}/checkout")
async def checkout(
    cart_id: str,
    body: Optional[CheckoutBody] = None,
    authorization: Optional[str] = Header(None),
    x_correlation_id: Optional[str] = Header(None),
    idempotency_key: Optional[str] = Header(None),
):
    # Timeout amplio: G4 llama de forma sincrona a G5 (crear pedido) y G8 (iniciar
    # pago / MercadoPago). Reenviamos {shippingAddress, notes} tal cual.
    payload = body.model_dump(exclude_none=True) if body else None
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{_g4_base()}/v1/cart/{cart_id}/checkout",
            json=payload,
            headers=_headers(authorization, x_correlation_id, idempotency_key, with_idempotency=True),
        )
    if response.status_code not in (200, 201, 202):
        _raise_from(response)
    if response.status_code == 204 or not response.content:
        return {"status": "PENDING"}
    data = response.json()
    # La respuesta ahora trae {status, paymentUrl} (no un carrito): pasa tal cual.
    return _normalize_cart(data) if _looks_like_cart(data) else data


@router.patch("/{cart_id}/cancel_checkout")
async def cancel_checkout(
    cart_id: str,
    authorization: Optional[str] = Header(None),
    x_correlation_id: Optional[str] = Header(None),
):
    # Libera el stock retenido por el checkout (G4). El front lo llama al cancelar
    # en las pantallas de datos de despacho o de pago.
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.patch(
            f"{_g4_base()}/v1/cart/{cart_id}/cancel_checkout",
            headers=_headers(authorization, x_correlation_id),
        )
    if response.status_code not in (200, 202, 204):
        _raise_from(response)
    if response.status_code == 204 or not response.content:
        return {"status": "CANCELLED"}
    data = response.json()
    return _normalize_cart(data) if _looks_like_cart(data) else data


@router.patch("/{cart_id}/activate")
async def activate_cart(
    cart_id: str,
    authorization: Optional[str] = Header(None),
    x_correlation_id: Optional[str] = Header(None),
):
    # "Salvavidas": libera la reserva (PENDING -> ACTIVE) cuando el usuario se
    # devuelve de despacho o cancela el pago, para no dejar stock retenido.
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.patch(
            f"{_g4_base()}/v1/cart/{cart_id}/activate",
            headers=_headers(authorization, x_correlation_id),
        )
    if response.status_code not in (200, 202, 204):
        _raise_from(response)
    if response.status_code == 204 or not response.content:
        return {"status": "ACTIVE"}
    body = response.json()
    return _normalize_cart(body) if _looks_like_cart(body) else body


@router.patch("/{cart_id}/complete")
async def complete_cart(
    cart_id: str,
    authorization: Optional[str] = Header(None),
    x_correlation_id: Optional[str] = Header(None),
    idempotency_key: Optional[str] = Header(None),
):
    # Cierre de la venta tras el pago exitoso: G4 confirma y genera el pedido
    # (orquesta G5). Reemplaza al viejo POST /v1/checkout. Devolvemos el body
    # tal cual porque aca viene el orderId que el front necesita mostrar/guardar.
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.patch(
            f"{_g4_base()}/v1/cart/{cart_id}/complete",
            headers=_headers(authorization, x_correlation_id, idempotency_key, with_idempotency=True),
        )
    if response.status_code not in (200, 201, 202):
        _raise_from(response)
    if response.status_code == 204 or not response.content:
        return {"status": "OK"}
    return response.json()
