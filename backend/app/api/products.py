import logging
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.auth import get_current_user
from app.models import Product
from app.schemas.products import ProductCreate, ProductResponse
from app.schemas.common import StandardResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/products", tags=["products"])


@router.post("", response_model=StandardResponse[ProductResponse], status_code=201)
def create_product(
    payload: ProductCreate,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    try:
        product = Product(**payload.model_dump())
        db.add(product)
        db.commit()
        db.refresh(product)
        return StandardResponse(data=ProductResponse.model_validate(product))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao criar produto: {e}", exc_info=True)
        raise HTTPException(500, detail="Erro interno do servidor.")


@router.get("", response_model=StandardResponse[list[ProductResponse]])
def list_products(
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    products = db.query(Product).filter(Product.is_active == True).all()
    return StandardResponse(data=[ProductResponse.model_validate(p) for p in products])


@router.get("/{product_id}", response_model=StandardResponse[ProductResponse])
def get_product(
    product_id: UUID,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    product = db.query(Product).filter(
        Product.id == product_id,
        Product.is_active == True
    ).first()
    if not product:
        raise HTTPException(404, detail="Produto nao encontrado.")
    return StandardResponse(data=ProductResponse.model_validate(product))


@router.delete("/{product_id}", response_model=StandardResponse[dict])
def delete_product(
    product_id: UUID,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    product = db.query(Product).filter(
        Product.id == product_id,
        Product.is_active == True
    ).first()
    if not product:
        raise HTTPException(404, detail="Produto nao encontrado.")
    product.is_active = False  # soft delete
    db.commit()
    return StandardResponse(data={"deleted": True, "id": str(product_id)})
