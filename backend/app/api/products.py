import json
import logging
import time
from datetime import datetime, timezone
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from typing import Literal
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.database import get_db
from app.auth import get_current_user
from app.models import Product, SEODescription, ProductImage, GenerationJob
from app.schemas.products import ProductCreate, ProductResponse
from app.schemas.common import StandardResponse
from app.services.seo_generator import SEOGeneratorService

logger = logging.getLogger(__name__)

# Rate limit: 1 geração SEO por produto a cada 30 segundos por usuário
_seo_rate_limit: dict[str, datetime] = {}
SEO_RATE_LIMIT_SECONDS = 30


def _check_seo_rate_limit(user_key: str, product_id: str) -> None:
    """
    Levanta HTTPException 429 se o usuário gerou SEO para este produto
    nos últimos SEO_RATE_LIMIT_SECONDS segundos.
    """
    key = f"{user_key}:{product_id}"
    now = datetime.now(timezone.utc)
    last = _seo_rate_limit.get(key)
    if last and (now - last).total_seconds() < SEO_RATE_LIMIT_SECONDS:
        remaining = SEO_RATE_LIMIT_SECONDS - int((now - last).total_seconds())
        raise HTTPException(
            429,
            detail=f"Aguarde {remaining}s antes de gerar SEO novamente para este produto."
        )
    _seo_rate_limit[key] = now


PlatformType = Literal["mercadolivre", "shopee", "shopify"]


class SEOGenerateRequest(BaseModel):
    platforms: list[PlatformType] = ["mercadolivre"]  # S14: default ML-only
    colors: list[str] = []
    image_id: str | None = None
    fabric: str | None = None
    gender_target: str | None = None
    sizing_info: str | None = None
    additional_notes: str | None = None
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


@router.get("/{product_id}/summary")
def get_product_summary(
    product_id: UUID,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    from app.services.url_helper import path_to_url

    product = db.query(Product).filter(
        Product.id == product_id,
        Product.is_active == True,
    ).first()
    if not product:
        raise HTTPException(404, detail="Produto não encontrado.")

    images = db.query(ProductImage).filter(
        ProductImage.product_id == product_id,
        ProductImage.type == "original",
    ).all()

    image_ids = [img.id for img in images]

    approved_jobs = db.query(GenerationJob).filter(
        GenerationJob.product_image_id.in_(image_ids),
        GenerationJob.type == "color_variation",
        GenerationJob.status == "approved",
        GenerationJob.deleted_at == None,
        GenerationJob.is_archived == False,
    ).all() if image_ids else []

    seo = db.query(SEODescription).filter(
        SEODescription.product_id == product_id,
    ).all()

    total_jobs = db.query(GenerationJob).filter(
        GenerationJob.product_image_id.in_(image_ids),
        GenerationJob.deleted_at == None,
    ).count() if image_ids else 0

    total_cost = db.query(
        func.sum(GenerationJob.cost_cents)
    ).filter(
        GenerationJob.product_image_id.in_(image_ids),
        GenerationJob.deleted_at == None,
    ).scalar() or 0 if image_ids else 0

    images_data = [{
        "id": str(img.id),
        "view": img.view,
        "original_url": img.original_url,
        "public_url": path_to_url(img.original_url) if img.original_url else None,
    } for img in images]

    approved_data = []
    for job in approved_jobs:
        result = json.loads(job.result) if job.result else {}
        approved_data.append({
            "id": str(job.id),
            "view": job.product_image.view if job.product_image else None,
            "color_hex": result.get("color_hex"),
            "jpg_url": result.get("jpg_url"),
        })

    seo_data = [{
        "platform": s.platform,
        "title": s.title,
        "description": s.description,
        "tags": json.loads(s.tags) if s.tags else [],
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    } for s in seo]

    return StandardResponse(data={
        "product": {
            "id": str(product.id),
            "name": product.name,
            "category": product.category,
            "fabric": product.fabric,
            "notes": product.notes,
            "created_at": product.created_at.isoformat(),
        },
        "images": images_data,
        "approved_variations": approved_data,
        "seo": seo_data,
        "stats": {
            "total_jobs": total_jobs,
            "total_cost_cents": total_cost,
            "total_cost_brl": round(total_cost * 0.006, 2),
            "views_uploaded": len(images),
            "variations_approved": len(approved_jobs),
            "platforms_with_seo": len(seo),
        },
    })


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
    current_user: dict = Depends(get_current_user),
):
    """
    Gera descrições SEO para o produto via Claude Vision.
    Usa a imagem de frente preferencialmente.
    """
    _check_seo_rate_limit(
        user_key=current_user.get("user_id", "default"),
        product_id=str(product_id)
    )

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

        operator_context = {
            k: v for k, v in {
                "fabric": payload.fabric,
                "gender_target": payload.gender_target,
                "sizing_info": payload.sizing_info,
                "additional_notes": payload.additional_notes,
            }.items() if v is not None
        }

        for platform in payload.platforms:
            try:
                plat_start = int(time.time() * 1000)
                result, tokens, warnings = svc.generate_for_platform(
                    garment_analysis=garment_analysis,
                    colors=payload.colors,
                    platform=platform,
                    operator_context=operator_context,
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
                    existing.updated_at = datetime.now(timezone.utc)
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
            "updated_at": d.updated_at.isoformat() if d.updated_at else d.created_at.isoformat(),
        }
        for d in descriptions
    ])
