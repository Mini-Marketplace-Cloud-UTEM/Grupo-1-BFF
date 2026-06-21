from fastapi import APIRouter, HTTPException, status

# TODO: implementar contra Grupo 4 (checkout) y Grupo 5 (lectura de pedidos).
# Decision ejecutiva 2026-06-19 (marketplace-contracts/decisiones-ejecutivas-2026-06-19.md #1):
# el BFF NO orquesta el checkout. POST /orders debe llamar a POST /v1/checkout de
# Grupo 4 (que ya orquesta con G5/G6/G8), no reimplementar la logica aqui.
# GET /orders y GET /orders/{orderId} leen de Grupo 5.

router = APIRouter(prefix="/orders", tags=["orders"])

_NOT_IMPLEMENTED = {"code": "NOT_IMPLEMENTED", "message": "Pendiente de implementar contra Grupo 4/Grupo 5."}


@router.post("")
async def create_order():
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_IMPLEMENTED)


@router.get("")
async def list_orders():
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_IMPLEMENTED)


@router.get("/{order_id}")
async def get_order(order_id: str):
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_IMPLEMENTED)
