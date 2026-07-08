import uuid

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Response, status

from app.config import settings
from app.dependencies import require_admin
from app.schemas import AuthenticatedUser

# Gestion admin de usuarios (proxy a Grupo 2). Contrato vivo verificado
# 2026-07-07 contra su openapi.json desplegado:
#
#   GET    /users            HTTPBearer requerido (la vuln de exponer todo
#                            sin token fue corregida por G2)
#   DELETE /users/{user_id}  HTTPBearer requerido, 204; body opcional
#                            {current_password} (no lo enviamos)
#
# G2 sigue en snake_case (avatar_url, created_at...) — aqui se traduce al
# camelCase de nuestro contrato. El shape exacto de GET /users no esta
# declarado en su openapi (schema vacio), por eso _extract_users tolera
# lista plana, {users: []} o {data: []}.
#
# Todo el acoplamiento con /users de G2 vive SOLO en este archivo: si G2
# vuelve a cambiar su contrato (siguen en transicion post-Supabase), este
# es el unico punto a tocar.

router = APIRouter(prefix="/admin/users", tags=["admin"])


def _g2_base() -> str:
    return settings.auth_service_url.rstrip("/")


def _headers(authorization: str) -> dict:
    return {
        "X-Request-Id": str(uuid.uuid4()),
        "X-Correlation-Id": str(uuid.uuid4()),
        "X-Consumer": "grupo1-bff",
        "Authorization": authorization,
    }


def _raise_from(response: httpx.Response):
    try:
        body = response.json()
    except ValueError:
        body = {}
    code = body.get("code") or ("UNAUTHORIZED" if response.status_code == 401 else "AUTH_SERVICE_ERROR")
    message = body.get("message") or (
        body.get("detail") if isinstance(body.get("detail"), str) else None
    ) or "Error en el servicio de identidad (Grupo 2)."
    raise HTTPException(status_code=response.status_code, detail={"code": code, "message": message})


def _extract_users(body) -> list:
    if isinstance(body, list):
        return body
    if isinstance(body, dict):
        for key in ("users", "data"):
            if isinstance(body.get(key), list):
                return body[key]
    return []


def _to_admin_user(u: dict) -> dict:
    return {
        "id": u.get("id"),
        "name": u.get("name"),
        "email": u.get("email"),
        "phone": u.get("phone"),
        "avatarUrl": u.get("avatar_url") or u.get("avatarUrl"),
        "roles": u.get("roles") or [],
        "active": u.get("active", True),
        "createdAt": u.get("created_at") or u.get("createdAt"),
        "updatedAt": u.get("updated_at") or u.get("updatedAt"),
    }


@router.get("")
async def list_users(
    admin: AuthenticatedUser = Depends(require_admin),
    # Header(None) para no duplicar la validacion: si falta el header,
    # require_admin ya corto antes con el 401 canonico.
    authorization: str = Header(None),
):
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(f"{_g2_base()}/users", headers=_headers(authorization))

    if response.status_code != 200:
        _raise_from(response)

    users = [_to_admin_user(u) for u in _extract_users(response.json())]
    total = len(users)
    # G2 no pagina (devuelve todo); se sintetiza la paginacion canonica para
    # que el frontend consuma la misma forma {data, pagination} de siempre.
    return {
        "data": users,
        "pagination": {
            "page": 1,
            "pageSize": total,
            "total": total,
            "totalPages": 1,
            "hasNext": False,
            "hasPrev": False,
        },
    }


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    admin: AuthenticatedUser = Depends(require_admin),
    authorization: str = Header(None),
):
    # Un admin no puede eliminarse a si mismo: quedaria un panel sin duenio y
    # es casi siempre un click accidental. La identidad sale del JWT validado
    # (admin.id), nunca de un campo del body.
    if admin.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "CANNOT_DELETE_SELF", "message": "Un administrador no puede eliminar su propia cuenta."},
        )

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.delete(f"{_g2_base()}/users/{user_id}", headers=_headers(authorization))

    if response.status_code not in (200, 204):
        _raise_from(response)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
