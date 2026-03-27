import json
import logging
import time
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db
from app.auth import get_current_user
from app.models import Product, SEODescription, ProductImage
from app.schemas.products import ProductCreate, ProductResponse
from app.schemas.common import StandardResponse
from app.services.seo_generator import SEOGeneratorService

logger = logging.getLogger(__name__)


class SEOGenerateRequest(BaseModel):
    platforms: list[str] = ["mercadolivre", "shopee", "shopify"]
    colors: list[str] = []
    image_id: str | None = None
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


@router.post("/{product_id}/seo", status_code=202)
def generate_seo(
    product_id: UUID,
    payload: SEOGenerateRequest,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """
    Gera descrições SEO para o produto via Claude Vision.
    Usa a imagem de frente preferencialmente.
    """
    product = db.query(Product).filter(
        Product.id == product_id, Product.is_active == True
    ).first()
    if not product:
        raise HTTPException(404, detail="Produto não encontrado.")

    if payload.image_id:
        image = db.query(ProductImage).filter(
            ProductImage.id == payload.image_id,
            ProductImage.product_id == product_id,
        ).first()
    else:
        image = db.query(ProductImage).filter(
            ProductImage.product_id == product_id,
            ProductImage.type == "original",
            ProductImage.view == "frente",
        ).first() or db.query(ProductImage).filter(
            ProductImage.product_id == product_id,
            ProductImage.type == "original",
        ).first()

    if not image:
        raise HTTPException(422, detail="Produto sem imagens. Faça upload primeiro.")

    image_path = image.processed_url or image.original_url
    if not image_path:
        raise HTTPException(422, detail="Imagem sem URL processada.")

    try:
        with open(image_path, "rb") as f:
            image_bytes = f.read()
    except FileNotFoundError:
        raise HTTPException(422, detail="Arquivo de imagem não encontrado no disco.")

    svc = SEOGeneratorService()
    results = []
    total_tokens = 0
    total_cost_cents = 0

    try:
        start = int(time.time() * 1000)
        garment_analysis, analysis_tokens = svc.analyze_garment(image_bytes)
        analysis_duration = int(time.time() * 1000) - start
        total_tokens += analysis_tokens

        for platform in payload.platforms:
            try:
                plat_start = int(time.time() * 1000)
                result, tokens, warnings = svc.generate_for_platform(
                    garment_analysis=garment_analysis,
                    colors=payload.colors,
                    platform=platform,
                )
                duration = int(time.time() * 1000) - plat_start
                total_tokens += tokens

                cost = max(1, round((tokens / 1000) * 3))
                total_cost_cents += cost

                if platform == "shopify":
                    title = result.get("title", "")
                    description = result.get("description_html", "")
                    tags = result.get("meta_keywords", [])
                else:
                    title = result.get("title", "")
                    description = result.get("description", "")
                    tags = result.get("keywords", result.get("tags", []))

                existing = db.query(SEODescription).filter(
                    SEODescription.product_id == product_id,
                    SEODescription.platform == platform,
                ).first()

                if existing:
                    existing.title = title
                    existing.description = description
                    existing.tags = json.dumps(tags, ensure_ascii=False)
                    existing.is_approved = False
                else:
                    seo = SEODescription(
                        product_id=product_id,
                        platform=platform,
                        title=title,
                        description=description,
                        tags=json.dumps(tags, ensure_ascii=False),
                    )
                    db.add(seo)

                db.commit()

                results.append({
                    "platform": platform,
                    "title": title,
                    "title_char_count": len(title),
                    "description_preview": description[:150] + "..." if len(description) > 150 else description,
                    "tags_count": len(tags),
                    "warnings": warnings,
                    "cost_cents": cost,
                    "duration_ms": duration,
                })

            except Exception as e:
                logger.error(f"Falha ao gerar SEO para {platform}: {e}", exc_info=True)
                results.append({
                    "platform": platform,
                    "error": str(e),
                    "cost_cents": 0,
                })

    except Exception as e:
        logger.error(f"Falha na análise da peça: {e}", exc_info=True)
        raise HTTPException(500, detail=f"Erro ao analisar peça: {str(e)}")

    return StandardResponse(data={
        "product_id": str(product_id),
        "garment_analysis": garment_analysis,
        "results": results,
        "total_tokens": total_tokens,
        "total_cost_cents": total_cost_cents,
    })


@router.get("/{product_id}/seo")
def get_seo_descriptions(
    product_id: UUID,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Lista todas as descrições SEO geradas para o produto."""
    product = db.query(Product).filter(
        Product.id == product_id, Product.is_active == True
    ).first()
    if not product:
        raise HTTPException(404, detail="Produto não encontrado.")

    descriptions = db.query(SEODescription).filter(
        SEODescription.product_id == product_id
    ).all()

    return StandardResponse(data=[
        {
            "id": str(d.id),
            "platform": d.platform,
            "title": d.title,
            "title_char_count": len(d.title),
            "description": d.description,
            "tags": json.loads(d.tags) if d.tags else [],
            "is_approved": d.is_approved,
            "created_at": d.created_at.isoformat(),
        }
        for d in descriptions
    ])
