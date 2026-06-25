import uuid
from datetime import date
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status

from app.config import settings
from app.dependencies import require_admin

# Contrato real (verificado en vivo 2026-06-23):
# https://grupo-7-reporter-a-bash-y-streaming-production.up.railway.app/docs
#
# G7 exige X-Request-Id/X-Correlation-Id/X-Consumer en todos los endpoints
# (salvo /health) y no valida JWT por su cuenta - el control de acceso
# (rol admin) lo hace este router antes de reenviar la llamada.
#
# Unica traduccion necesaria: la paginacion de /reports/top-products usa
# {totalItems, totalPages, currentPage, pageSize} en vez de nuestro
# {page, pageSize, total, totalPages, hasNext, hasPrev}. El resto de los
# campos ya viene en camelCase y coincide con nuestra convencion.

router = APIRouter(prefix="/admin/reports", tags=["reports"])


def _g7_headers(extra: Optional[dict] = None) -> dict:
    headers = {
        "X-Request-Id": str(uuid.uuid4()),
        "X-Correlation-Id": str(uuid.uuid4()),
        "X-Consumer": "grupo1-bff",
    }
    if extra:
        headers.update(extra)
    return headers


def _raise_from(response: httpx.Response):
    raise HTTPException(
        status_code=response.status_code,
        detail={"code": "UPSTREAM_ERROR", "message": "Error al consultar el servicio de Reportería."},
    )


async def _get_report(path: str, params: Optional[dict] = None) -> dict:
    base_url = settings.reports_service_url.rstrip("/")
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(f"{base_url}{path}", params=params, headers=_g7_headers())

    if response.status_code != 200:
        _raise_from(response)
    return response.json()


@router.get("/sales", dependencies=[Depends(require_admin)])
async def sales_report(from_: Optional[date] = Query(None, alias="from"), to: Optional[date] = None):
    params = {}
    if from_:
        params["from"] = str(from_)
    if to:
        params["to"] = str(to)
    return await _get_report("/reports/sales", params)


@router.get("/orders-by-status", dependencies=[Depends(require_admin)])
async def orders_by_status_report():
    return await _get_report("/reports/orders-by-status")


@router.get("/top-products", dependencies=[Depends(require_admin)])
async def top_products_report(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=100)):
    body = await _get_report("/reports/top-products", {"page": page, "pageSize": pageSize})
    p = body["pagination"]
    current_page = p["currentPage"]
    total_pages = p["totalPages"]

    return {
        "data": body["data"],
        "pagination": {
            "page": current_page,
            "pageSize": p["pageSize"],
            "total": p["totalItems"],
            "totalPages": total_pages,
            "hasNext": current_page < total_pages,
            "hasPrev": current_page > 1,
        },
    }


@router.get("/average-ticket", dependencies=[Depends(require_admin)])
async def average_ticket_report():
    return await _get_report("/reports/average-ticket")


@router.get("/peak-hours", dependencies=[Depends(require_admin)])
async def peak_hours_report():
    return await _get_report("/reports/peak-hours")


@router.get("/delivery-performance", dependencies=[Depends(require_admin)])
async def delivery_performance_report():
    return await _get_report("/reports/delivery-performance")


@router.post("/batch/recalculate", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(require_admin)])
async def trigger_batch_recalculate(
    body: Optional[dict] = None,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    base_url = settings.reports_service_url.rstrip("/")
    headers = _g7_headers({"Idempotency-Key": idempotency_key or str(uuid.uuid4())})

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(f"{base_url}/reports/batch/recalculate", json=body, headers=headers)

    if response.status_code != 202:
        _raise_from(response)
    return response.json()
