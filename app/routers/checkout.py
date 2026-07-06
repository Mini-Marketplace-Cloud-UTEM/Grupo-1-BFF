from typing import Optional

import httpx
from fastapi import APIRouter, Header
from pydantic import BaseModel

from app.routers.cart import _g4_base, _headers, _raise_from

# Checkout lo ORQUESTA Grupo 4 (decision ejecutiva 2026-06-28): el BFF solo
# consume POST /v1/checkout, no reimplementa la orquestacion G4->G5->G8.
# Contrato real G4 v1.2.0:
#   POST /v1/checkout                body: {cartId}   (con Idempotency-Key)
#   GET  /v1/checkout/{checkout_id}  estado del checkout

router = APIRouter(prefix="/checkout", tags=["checkout"])


class CheckoutBody(BaseModel):
    cartId: str


@router.post("")
async def initiate_checkout(
    body: CheckoutBody,
    authorization: Optional[str] = Header(None),
    x_correlation_id: Optional[str] = Header(None),
    idempotency_key: Optional[str] = Header(None),
):
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            f"{_g4_base()}/v1/checkout",
            json={"cartId": body.cartId},
            headers=_headers(authorization, x_correlation_id, idempotency_key, with_idempotency=True),
        )
    if response.status_code not in (200, 201, 202):
        _raise_from(response)
    # G4 no documenta la forma de la respuesta; la devolvemos tal cual.
    try:
        return response.json()
    except ValueError:
        return {"status": "OK"}


@router.get("/{checkout_id}")
async def get_checkout_status(
    checkout_id: str,
    authorization: Optional[str] = Header(None),
    x_correlation_id: Optional[str] = Header(None),
):
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            f"{_g4_base()}/v1/checkout/{checkout_id}",
            headers=_headers(authorization, x_correlation_id),
        )
    if response.status_code != 200:
        _raise_from(response)
    try:
        return response.json()
    except ValueError:
        return {"status": "UNKNOWN"}
