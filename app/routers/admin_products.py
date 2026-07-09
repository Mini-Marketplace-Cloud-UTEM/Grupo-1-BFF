import uuid
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from pydantic import BaseModel

from app.config import settings
from app.dependencies import require_admin

# Mutaciones admin de productos (proxy a Grupo 3) + consulta de inventario
# (proxy a Grupo 4). Contratos reales verificados en vivo 2026-07-07 contra
# los openapi.json desplegados:
#
#   G3: POST /products            body camelCase {name*, price*, categoryId*,
#                                 description, stockVisible, sku, images[]}
#       PUT  /products/{id}       UpdateProductRequest SIN categoryId (la
#                                 categoria es inmutable tras crear)
#       DELETE /products/{id}     204, soft-delete (status=DELETED)
#       Todas aceptan idempotency-key y authorization opcionales.
#
#   G4: GET /v1/inventory/{productId} -> {productId, stockTotal,
#                                 reservedQuantity, availableStock}
#       Bug conocido: G4 puede no reconocer productos reales de G3 (404);
#       el frontend trata el inventario como dato opcional, nunca bloqueante.
#
# Seguridad: G3 y G4 NO validan rol admin de su lado — el gate es nuestro
# Depends(require_admin) (Bearer -> POST /auth/validate de G2 -> roles).
# Igual reenviamos el Authorization del admin aguas arriba por si algun
# grupo empieza a validar (el header ya es aceptado como opcional).

router = APIRouter(prefix="/admin", tags=["admin"])


class CreateProductBody(BaseModel):
    name: str
    price: int
    categoryId: str
    description: Optional[str] = None
    stockVisible: int = 0
    sku: Optional[str] = None
    images: list[str] = []


class UpdateProductBody(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[int] = None
    stockVisible: Optional[int] = None
    status: Optional[str] = None
    images: Optional[list[str]] = None


def _g3_base() -> str:
    return settings.catalog_service_url.rstrip("/")


def _g4_base() -> str:
    return settings.cart_service_url.rstrip("/")


def _headers(authorization: Optional[str] = None, idempotency_key: Optional[str] = None) -> dict:
    headers = {
        "X-Request-Id": str(uuid.uuid4()),
        "X-Correlation-Id": str(uuid.uuid4()),
        "X-Consumer": "grupo1-bff",
    }
    if authorization:
        headers["Authorization"] = authorization
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    return headers


def _raise_from_g3(response: httpx.Response):
    try:
        body = response.json()
    except ValueError:
        body = {}
    raise HTTPException(
        status_code=response.status_code,
        detail={"code": body.get("code", "ERROR"), "message": body.get("message", "Error en Grupo 3.")},
    )


def _raise_from_g4(response: httpx.Response):
    try:
        body = response.json()
    except ValueError:
        body = {}
    # G4 no usa el error canonico: puede venir {error, message} o {detail}.
    code = body.get("code") or ("NOT_FOUND" if response.status_code == 404 else "INVENTORY_ERROR")
    message = body.get("message") or body.get("error") or (
        body.get("detail") if isinstance(body.get("detail"), str) else None
    ) or "Error en el servicio de inventario (Grupo 4)."
    raise HTTPException(status_code=response.status_code, detail={"code": code, "message": message})


def _to_admin_product(p: dict) -> dict:
    # A diferencia del _to_summary de catalog.py, aqui se conserva sku y el
    # stock/status crudos: es la vista de administracion, no la de tienda.
    return {
        "id": p["id"],
        "name": p["name"],
        "description": p.get("description"),
        "price": round(p["price"]),
        "currency": "CLP",
        "stock": p.get("stockVisible", 0),
        "categoryId": p.get("categoryId"),
        "categoryName": p.get("categoryName"),
        "sku": p.get("sku"),
        "status": p.get("status"),
        "images": p.get("images", []),
        "createdAt": p.get("createdAt"),
        "updatedAt": p.get("updatedAt"),
    }


@router.post("/products", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_admin)])
async def create_product(
    body: CreateProductBody,
    authorization: Optional[str] = Header(None),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    headers = _headers(authorization, idempotency_key or str(uuid.uuid4()))
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(f"{_g3_base()}/products", json=body.model_dump(exclude_none=True), headers=headers)

    if response.status_code not in (200, 201):
        _raise_from_g3(response)
    return _to_admin_product(response.json())


@router.put("/products/{product_id}", dependencies=[Depends(require_admin)])
async def update_product(
    product_id: str,
    body: UpdateProductBody,
    authorization: Optional[str] = Header(None),
):
    payload = body.model_dump(exclude_unset=True)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "VALIDATION_ERROR", "message": "El body no trae ningún campo para actualizar."},
        )

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.put(
            f"{_g3_base()}/products/{product_id}", json=payload, headers=_headers(authorization)
        )

    if response.status_code != 200:
        _raise_from_g3(response)
    return _to_admin_product(response.json())


@router.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_admin)])
async def delete_product(product_id: str, authorization: Optional[str] = Header(None)):
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.delete(f"{_g3_base()}/products/{product_id}", headers=_headers(authorization))

    if response.status_code not in (200, 204):
        _raise_from_g3(response)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/inventory/{product_id}", dependencies=[Depends(require_admin)])
async def get_inventory(product_id: str, authorization: Optional[str] = Header(None)):
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(f"{_g4_base()}/v1/inventory/{product_id}", headers=_headers(authorization))

    if response.status_code != 200:
        _raise_from_g4(response)

    # El G4 vivo (2026-07-07) devuelve {productId, stockVisible,
    # reservas_activas} — distinto a su propio contrato ({stockTotal,
    # reservedQuantity, availableStock}) y con un campo en snake_case.
    # Se aceptan ambas formas por si G4 se alinea a su contrato despues.
    body = response.json()
    stock_total = body.get("stockTotal", body.get("stockVisible"))
    reserved = body.get("reservedQuantity", body.get("reservas_activas")) or 0
    available = body.get("availableStock")
    if available is None and stock_total is not None:
        available = stock_total - reserved
    return {
        "productId": body.get("productId", product_id),
        "stockTotal": stock_total,
        "reservedQuantity": reserved,
        "availableStock": available,
    }
