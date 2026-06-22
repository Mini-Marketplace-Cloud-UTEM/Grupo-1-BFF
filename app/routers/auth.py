import httpx
from fastapi import APIRouter, Header, HTTPException, status

from app.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])


def _translate_tokens(g2_response: dict) -> dict:
    # G2 responde en snake_case; el contrato BFF expone camelCase.
    return {
        "accessToken": g2_response["access_token"],
        "refreshToken": g2_response["refresh_token"],
        "tokenType": g2_response["token_type"],
        "expiresIn": g2_response["expires_in"],
    }


def _translate_user(g2_user: dict) -> dict:
    return {
        "id": g2_user["id"],
        "name": g2_user.get("name"),
        "email": g2_user.get("email"),
        "phone": g2_user.get("phone"),
        "avatarUrl": g2_user.get("avatar_url"),
    }


@router.post("/login")
async def login(body: dict):
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(f"{settings.auth_service_url}/auth/login", json=body)

    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.json())

    return _translate_tokens(response.json())


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(authorization: str = Header(...)):
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            f"{settings.auth_service_url}/auth/logout",
            headers={"Authorization": authorization},
        )

    if response.status_code != 204:
        raise HTTPException(status_code=response.status_code, detail=response.json())


@router.post("/refresh")
async def refresh(body: dict):
    g2_body = {"refresh_token": body["refreshToken"]}

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(f"{settings.auth_service_url}/auth/refresh", json=g2_body)

    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.json())

    return _translate_tokens(response.json())


@router.get("/me")
async def me(authorization: str = Header(...)):
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            f"{settings.auth_service_url}/auth/me",
            headers={"Authorization": authorization},
        )

    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.json())

    return _translate_user(response.json())
