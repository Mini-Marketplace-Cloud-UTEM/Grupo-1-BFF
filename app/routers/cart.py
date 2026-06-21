from fastapi import APIRouter, HTTPException, status

# TODO: implementar contra Grupo 4 (Carro/Checkout/Inventario).
# Contrato real: marketplace-contracts/services/group-4-carrito/openapi.yaml
# URL: settings.cart_service_url (hoy solo mock Prism local, ver registro-de-servicios.md)

router = APIRouter(prefix="/cart", tags=["cart"])

_NOT_IMPLEMENTED = {"code": "NOT_IMPLEMENTED", "message": "Pendiente de implementar contra Grupo 4."}


@router.get("")
async def get_cart():
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_IMPLEMENTED)


@router.delete("")
async def clear_cart():
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_IMPLEMENTED)


@router.post("/items")
async def add_item():
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_IMPLEMENTED)


@router.patch("/items/{item_id}")
async def update_item(item_id: str):
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_IMPLEMENTED)


@router.delete("/items/{item_id}")
async def remove_item(item_id: str):
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_IMPLEMENTED)
