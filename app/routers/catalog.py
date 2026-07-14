import re
import uuid
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Query

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
# (queda en canonical-models.md como gap conocido). GET /categories ya
# existe en G3 (verificado en vivo 2026-07-07) y aca se proxea de verdad.
#
# 2026-06-28: el dinero sigue siendo entero, pero ahora de 64 bits
# (int64/"long" en vez de 32 bits) - el evaluador de la asignatura exigio
# este cambio de ancho en todo el proyecto (ver marketplace-contracts,
# guia-y-lineamiento-de-desarrollo.md seccion 2). En Python no hay
# distincion int32/int64 (int es de precision arbitraria), por eso
# round() sigue siendo correcto aqui.

router = APIRouter(tags=["catalog"])


def _g3_headers() -> dict:
    return {
        "X-Request-Id": str(uuid.uuid4()),
        "X-Correlation-Id": str(uuid.uuid4()),
        "X-Consumer": "grupo1-bff",
    }


# Cache simple nombre(lower) -> categoryId de G3. El front filtra por NOMBRE de
# categoria (su sidebar/landing usan nombres), pero G3 filtra por categoryId
# (UUID). Resolvemos aca. Se refresca si falta la clave (categoria nueva); las
# categorias casi no cambian, asi que basta.
_category_id_cache: dict = {}


async def _resolve_category_id(client: httpx.AsyncClient, base_url: str, category: str) -> Optional[str]:
    if not category:
        return None
    # Si ya viene un UUID, usarlo tal cual (soporta ambos: nombre o id).
    try:
        uuid.UUID(str(category))
        return str(category)
    except (ValueError, AttributeError, TypeError):
        pass
    key = str(category).strip().lower()
    if key in _category_id_cache:
        return _category_id_cache[key]
    try:
        resp = await client.get(
            f"{base_url}/categories", params={"page": 1, "size": 100}, headers=_g3_headers()
        )
        if resp.status_code == 200:
            for c in resp.json().get("data", []):
                if c.get("name") and c.get("id"):
                    _category_id_cache[c["name"].strip().lower()] = c["id"]
    except httpx.HTTPError:
        return None
    return _category_id_cache.get(key)


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
        # Tamaño del producto (talla de paquete XS..XXL). G3 lo agrego como
        # campo del producto (lo consume G4 para cotizar el despacho con G6).
        "size": p.get("size"),
        # Campos extra para el panel admin (el front de cliente los ignora).
        "categoryId": p.get("categoryId"),
        "stock": p.get("stockVisible", 0),
        "status": p.get("status"),
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
        # El front manda la categoria por NOMBRE (o 'all'); G3 filtra por
        # categoryId (UUID). Resolvemos antes de reenviar (soporta tambien un id).
        category_id = None
        if category and str(category).strip().lower() != "all":
            category_id = await _resolve_category_id(client, base_url, category)

        if q:
            params = {"q": q, "page": page, "size": pageSize}
            if category_id:
                params["categoryId"] = category_id
            response = await client.get(f"{base_url}/products/search", params=params, headers=_g3_headers())
        else:
            params = {"page": page, "size": pageSize}
            if category_id:
                params["categoryId"] = category_id
            response = await client.get(f"{base_url}/products", params=params, headers=_g3_headers())

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


@router.get("/categories")
async def list_categories(page: int = Query(1, ge=1), pageSize: int = Query(100, ge=1, le=100)):
    # pageSize default 100: el consumidor principal es el select del form de
    # productos del panel admin, que necesita todas las categorias de una.
    base_url = settings.catalog_service_url.rstrip("/")

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            f"{base_url}/categories", params={"page": page, "size": pageSize}, headers=_g3_headers()
        )

    if response.status_code != 200:
        _raise_from(response)

    # G3 ya devuelve {data: [{id, name}], pagination} canonico - passthrough.
    return response.json()
