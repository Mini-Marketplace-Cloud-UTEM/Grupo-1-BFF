from fastapi import APIRouter, HTTPException, status

# TODO: implementar contra Grupo 3 (Catalogo).
# Contrato real: marketplace-contracts/services/group-3-catalogo/openapi.yaml
# URL: settings.catalog_service_url (hoy solo mock Prism local, ver registro-de-servicios.md)

router = APIRouter(tags=["catalog"])

_NOT_IMPLEMENTED = {"code": "NOT_IMPLEMENTED", "message": "Pendiente de implementar contra Grupo 3."}


@router.get("/products")
async def list_products():
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_IMPLEMENTED)


@router.get("/products/{product_id}")
async def get_product(product_id: str):
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_IMPLEMENTED)


@router.get("/categories")
async def list_categories():
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_IMPLEMENTED)
