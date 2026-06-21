from typing import Any, Optional

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    field: str
    message: str


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: Optional[list[ErrorDetail]] = None
    correlationId: Optional[str] = None


class Pagination(BaseModel):
    page: int
    pageSize: int
    total: int
    totalPages: int
    hasNext: bool
    hasPrev: bool


class AuthenticatedUser(BaseModel):
    id: str
    roles: list[str] = []
    raw: dict[str, Any] = {}
