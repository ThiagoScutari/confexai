import json
import logging
import os
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import get_current_user
from app.models import GenerationJob, JobType, JobStatus, ProductImage
from app.schemas.common import StandardResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])

ANTHROPIC_COST_PER_1K_TOKENS_CENTS = 3  # ~$0.03 por 1K tokens de input, ~R$0.18


@router.post("/detect-protected-regions", status_code=202)
def detect_protected_regions(
    payload: dict,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """
    Dispara deteccao de regioes protegidas em uma imagem via Claude Vision.
    payload: { "product_image_id": "uuid" }
    """
    from app.services.protected_regions import detect_protected_regions as svc_detect
    from datetime import datetime

    image_id = payload.get("product_image_id")
    if not image_id:
        raise HTTPException(422, detail="product_image_id e obrigatorio.")

    image = db.query(ProductImage).filter(
        ProductImage.id == image_id,
        ProductImage.is_active == True,
    ).first()
    if not image:
        raise HTTPException(404, detail="Imagem nao encontrada.")

    # Usar processed_url se disponivel (fundo removido), senao original
    image_path = image.processed_url or image.original_url
    if not image_path:
        raise HTTPException(422, detail="Imagem sem URL processada.")

    job = GenerationJob(
        product_image_id=image_id,
        type=JobType.protected_region_detection,
        status=JobStatus.processing,
        api_used="anthropic",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        with open(image_path, "rb") as f:
            image_bytes = f.read()

        result = svc_detect(image_bytes)

        tokens = result.get("tokens_used", 0)
        cost = (tokens / 1000) * ANTHROPIC_COST_PER_1K_TOKENS_CENTS

        job.status = JobStatus.done
        job.tokens_used = tokens
        job.cost_cents = round(cost)
        job.result = json.dumps(result, ensure_ascii=False)
        job.completed_at = datetime.utcnow()
        db.commit()

        return StandardResponse(data={
            "job_id": str(job.id),
            "status": "done",
            "has_protected_regions": result.get("has_protected_regions", False),
            "regions_count": len(result.get("protected_regions", [])),
            "cost_cents": job.cost_cents,
        })

    except Exception as e:
        job.status = JobStatus.failed
        job.error_message = str(e)
        db.commit()
        logger.error(f"Falha na deteccao de regioes: {e}", exc_info=True)
        raise HTTPException(500, detail="Erro interno do servidor.")


class ColorVariationRequest(BaseModel):
    product_image_id: str
    target_colors: list[str]          # lista de HEX: ["#696980", "#978b7b"]
    protected_regions: list[dict] = [] # vindo do job de deteccao


@router.post("/color-variation", status_code=202)
def create_color_variation(
    payload: ColorVariationRequest,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    from app.services.color_variation import apply_color_variation
    from datetime import datetime
    from pathlib import Path

    image = db.query(ProductImage).filter(
        ProductImage.id == payload.product_image_id,
        ProductImage.is_active == True,
    ).first()
    if not image:
        raise HTTPException(404, detail="Imagem nao encontrada.")

    image_path = image.processed_url or image.original_url
    if not image_path:
        raise HTTPException(422, detail="Imagem sem URL processada.")

    results = []
    total_cost = 0

    with open(image_path, "rb") as f:
        image_bytes = f.read()

    for color_hex in payload.target_colors:
        safe_hex = color_hex.replace("#", "").upper()
        view_suffix = f"_{image.view}" if image.view else ""
        output_path = Path(image_path).parent / f"color_{safe_hex}{view_suffix}.png"

        job = GenerationJob(
            product_image_id=payload.product_image_id,
            type=JobType.color_variation,
            status=JobStatus.processing,
            api_used="gemini",
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        try:
            result = apply_color_variation(
                image_bytes=image_bytes,
                target_hex=color_hex,
                protected_regions=payload.protected_regions,
                output_path=output_path,
            )

            # Registrar variante no banco
            variant = ProductImage(
                product_id=image.product_id,
                type="color_variant",
                view=image.view,
                original_url=image.original_url,
                processed_url=result["png_url"],
                color_hex=color_hex,
            )
            db.add(variant)

            method = result.get("method", "gemini")
            job.status = JobStatus.pending_review
            job.api_used = "gemini" if method == "gemini" else "gemini_fallback_pillow"
            job.cost_cents = result["cost_cents"]
            job.result = json.dumps(result, ensure_ascii=False)
            job.completed_at = datetime.utcnow()
            total_cost += result["cost_cents"]
            db.commit()

            results.append({
                "job_id": str(job.id),
                "color_hex": color_hex,
                "status": "pending_review",
                "png_url": result["png_url"],
                "jpg_url": result["jpg_url"],
                "cost_cents": result["cost_cents"],
                "method": method,
                "view": image.view,
            })

        except Exception as e:
            job.status = JobStatus.failed
            job.error_message = str(e)
            db.commit()
            logger.error(f"Falha na variacao de cor {color_hex}: {e}", exc_info=True)
            results.append({
                "job_id": str(job.id),
                "color_hex": color_hex,
                "status": "failed",
                "error": str(e),
            })

    return StandardResponse(data={
        "results": results,
        "total_cost_cents": total_cost,
    })


class RejectRequest(BaseModel):
    reason: str


@router.get("")
def list_jobs(
    product_id: str | None = None,
    type: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    query = db.query(GenerationJob)

    if product_id:
        query = query.join(ProductImage).filter(
            ProductImage.product_id == product_id
        )
    if type:
        query = query.filter(GenerationJob.type == type)
    if status:
        query = query.filter(GenerationJob.status == status)

    jobs = query.order_by(GenerationJob.created_at.desc()).limit(100).all()

    return StandardResponse(data=[
        {
            "id": str(j.id),
            "type": j.type.value,
            "status": j.status.value,
            "api_used": j.api_used,
            "cost_cents": j.cost_cents,
            "result": json.loads(j.result) if j.result else None,
            "created_at": j.created_at.isoformat(),
            "completed_at": j.completed_at.isoformat() if j.completed_at else None,
            "product_id": str(j.product_image.product_id) if j.product_image else None,
            "view": j.product_image.view if j.product_image else None,
        }
        for j in jobs
    ])


@router.get("/{job_id}")
def get_job(
    job_id: UUID,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    job = db.query(GenerationJob).filter(GenerationJob.id == job_id).first()
    if not job:
        raise HTTPException(404, detail="Job nao encontrado.")
    return StandardResponse(data={
        "id": str(job.id),
        "type": job.type.value,
        "status": job.status.value,
        "api_used": job.api_used,
        "cost_cents": job.cost_cents,
        "result": json.loads(job.result) if job.result else None,
        "error_message": job.error_message,
        "created_at": job.created_at.isoformat(),
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    })


@router.post("/{job_id}/approve")
def approve_job(
    job_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    from datetime import datetime
    job = db.query(GenerationJob).filter(GenerationJob.id == job_id).first()
    if not job:
        raise HTTPException(404, detail="Job nao encontrado.")
    if job.status != JobStatus.pending_review:
        raise HTTPException(409, detail=f"Job nao esta em revisao. Status atual: {job.status.value}")
    job.status = JobStatus.approved
    job.approved_at = datetime.utcnow()
    job.approved_by = current_user.get("email", "unknown")
    db.commit()
    return StandardResponse(data={
        "job_id": str(job_id),
        "status": "approved",
        "approved_at": job.approved_at.isoformat(),
    })


@router.post("/{job_id}/reject")
def reject_job(
    job_id: UUID,
    payload: RejectRequest,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    job = db.query(GenerationJob).filter(GenerationJob.id == job_id).first()
    if not job:
        raise HTTPException(404, detail="Job nao encontrado.")
    if job.status not in (JobStatus.pending_review, JobStatus.done):
        raise HTTPException(409, detail=f"Job nao pode ser rejeitado. Status: {job.status.value}")
    job.status = JobStatus.rejected
    job.rejection_reason = payload.reason
    db.commit()
    return StandardResponse(data={
        "job_id": str(job_id),
        "status": "rejected",
        "reason": payload.reason,
    })
