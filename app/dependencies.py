import httpx
from fastapi import Header, HTTPException, status

from app.config import settings
from app.schemas import AuthenticatedUser

# Validacion centralizada vía POST /auth/validate de Grupo 2.
# Decision ejecutiva 2026-06-19 (marketplace-contracts/data-dictionary/estandar-jwt.md):
# ningun servicio verifica la firma del JWT localmente.


async def get_current_user(authorization: str = Header(...)) -> AuthenticatedUser:
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Falta el header Authorization Bearer."},
        )

    async with httpx.AsyncClient(timeout=5.0) as client:
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
