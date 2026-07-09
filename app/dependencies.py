from typing import Optional

import httpx
from fastapi import Depends, Header, HTTPException, status

from app.config import settings
from app.schemas import AuthenticatedUser

# Validacion centralizada vía POST /auth/validate de Grupo 2.
# Decision ejecutiva 2026-06-19 (marketplace-contracts/data-dictionary/estandar-jwt.md):
# ningun servicio verifica la firma del JWT localmente.


async def get_current_user(authorization: Optional[str] = Header(None)) -> AuthenticatedUser:
    # Header(None) y no Header(...): si falta el header, FastAPI generaria un
    # 422 de validacion con {detail}, rompiendo el error canonico. Aca falta
    # de header y header malformado responden igual: 401 {code, message}.
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Falta el header Authorization Bearer."},
        )

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            f"{settings.auth_service_url}/auth/validate",
            headers={"Authorization": authorization},
        )

    if response.status_code != 200 or not response.json().get("valid"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Token invalido o expirado."},
        )

    user = response.json()["user"]
    return AuthenticatedUser(id=user["id"], roles=user.get("roles", []), raw=user)


async def require_admin(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
    if "admin" not in user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "Se requiere rol admin."},
        )
    return user
