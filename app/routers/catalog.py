import re
import uuid
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Query, status

from app.config import settings

# Contrato real: marketplace-contracts/services/group-3-catalogo/openapi.yaml
# OJO: ese openapi.yaml describe la API en snake_case (stock_visible,
# category_id...) pero el servicio REAL desplegado (verificado en vivo
# 2026-06-22) ya responde en camelCase (stockVisible, categoryId,
# categoryName, pageSize) y con error plano {code, message, correlationId}.
# El codigo de abajo esta escrito contra lo que el servicio real devuelve
# HOY, no contra lo que dice su YAML - hay que avisarle a G3 que actualice
# su contrato comiteado.
#
# G3 no soporta minPrice/maxPrice/sortBy ni categoria por nombre (solo
# category_id en /products/search) - se ignoran en silencio por ahora
# (queda en canonical-models.md como gap conocido). /categories tampoco
# existe en G3 todavia, sigue como stub.

router = APIRouter(tags=["catalog"])


def _g3_headers() -> dict:
    return {
        "X-Request-Id": str(uuid.uuid4()),
        "X-Correlation-Id": str(uuid.uuid4()),
        "X-Consumer": "grupo1-bff",
    }


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug


def _to_summary(p: dict) -> dict:
    return {
        "id": p["id"],
        "name": p["name"],
        "slug": _slugify(p["name"]),
        "price": round(p["price"]),
        "currency": "CLP",
        "imageUrl": (p.get("images") or [None])[0],
        "category": p.get("categoryName"),
        "inStock": p.get("stockVisible", 0) > 0,
    }


def _to_detail(p: dict) -> dict:
    summary = _to_summary(p)
    summary.update(
        description=p.get("description"),
        images=p.get("images", []),
        stock=p.get("stockVisible", 0),
        attributes={},
        createdAt=p.get("createdAt"),
        updatedAt=p.get("updatedAt"),
    )
    return summary


def _raise_from(response: httpx.Response):
    try:
        body = response.json()
    except ValueError:
        body = {}
    raise HTTPException(
        status_code=response.status_code,
        detail={"code": body.get("code", "ERROR"), "message": body.get("message", "Error en Grupo 3.")},
    )


@router.get("/products")
async def list_products(
    q: Optional[str] = None,
    category: Optional[str] = None,
    minPrice: Optional[int] = None,
    maxPrice: Optional[int] = None,
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    sortBy: Optional[str] = None,
):
    base_url = settings.catalog_service_url.rstrip("/")

    async with httpx.AsyncClient(timeout=20.0) as client:
        if q:
            params = {"q": q, "page": page, "size": pageSize}
            if category:
                params["category_id"] = category
            response = await client.get(f"{base_url}/products/search", params=params, headers=_g3_headers())
        else:
            response = await client.get(
                f"{base_url}/products", params={"page": page, "size": pageSize}, headers=_g3_headers()
            )

    if response.status_code != 200:
        _raise_from(response)

    body = response.json()
    pagination = body["pagination"]

    return {
        "data": [_to_summary(p) for p in body["data"]],
        "pagination": pagination,
        "filters": {"q": q, "category": category, "minPrice": minPrice, "maxPrice": maxPrice},
    }


@router.get("/products/{product_id}")
async def get_product(product_id: str):
    base_url = settings.catalog_service_url.rstrip("/")

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(f"{base_url}/products/{product_id}", headers=_g3_headers())

    if response.status_code != 200:
        _raise_from(response)

    return _to_detail(response.json())


# G3 todavia no expone GET /categories - no hay endpoint real contra el que implementar esto.
_NOT_IMPLEMENTED = {"code": "NOT_IMPLEMENTED", "message": "Grupo 3 todavia no expone un endpoint de categorias."}


@router.get("/categories")
async def list_categories():
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_IMPLEMENTED)
