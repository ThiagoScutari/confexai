import json
import logging
import os
import io
import zipfile
from uuid import UUID
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import get_current_user
from app.models import GenerationJob, JobType, JobStatus, ProductImage
from app.schemas.common import StandardResponse
from app.services.url_helper import path_to_url

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


def _prefetch_product_names(db, jobs: list) -> dict:
    """Busca nomes de produtos em UMA query. Evita N+1."""
    product_ids = set()
    for j in jobs:
        if j.product_image:
            product_ids.add(j.product_image.product_id)
    if not product_ids:
        return {}
    from app.models import Product
    prods = db.query(Product).filter(Product.id.in_(product_ids)).all()
    return {str(p.id): p.name for p in prods}

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
        job.prompt_used = result.get("prompt_used")
        job.model_used = result.get("model_used")
        job.duration_ms = result.get("duration_ms")
        job.input_image_url = path_to_url(image_path)

        api_log_data = result.get("api_log")
        if api_log_data:
            from app.models import JobApiLog
            api_log = JobApiLog(
                job_id=job.id,
                request_payload=api_log_data.get("request_payload"),
                response_payload=api_log_data.get("response_payload"),
                http_status=api_log_data.get("http_status", 200),
            )
            db.add(api_log)

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

        job = GenerationJob(
            product_image_id=payload.product_image_id,
            type=JobType.color_variation,
            status=JobStatus.processing,
            api_used="gemini",
        )
        db.add(job)
        db.flush()  # gera job.id sem commitar

        job_short_id = str(job.id)[:8]
        output_path = Path(image_path).parent / f"color_{safe_hex}{view_suffix}_{job_short_id}.png"

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
            job.api_used = method
            job.cost_cents = result.get("cost_cents", 0)
            job.result = json.dumps(result, ensure_ascii=False)
            job.completed_at = datetime.utcnow()
            job.prompt_used = result.get("prompt_used")
            job.model_used = result.get("model_used")
            job.duration_ms = result.get("duration_ms")
            job.input_image_url = path_to_url(image_path)
            job.fallback_reason = result.get("fallback_reason")
            total_cost += result["cost_cents"]

            api_log_data = result.get("api_log")
            if api_log_data:
                from app.models import JobApiLog
                api_log = JobApiLog(
                    job_id=job.id,
                    request_payload=api_log_data.get("request_payload"),
                    response_payload=api_log_data.get("response_payload"),
                    http_status=api_log_data.get("http_status", 200),
                )
                db.add(api_log)

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


@router.patch("/{job_id}/delete")
def soft_delete_job(
    job_id: UUID,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """
    Marca job como excluído (deleted_at). Não aparece mais em nenhuma listagem.
    O registro permanece no banco para auditoria.
    """
    from datetime import datetime

    job = db.query(GenerationJob).filter(
        GenerationJob.id == job_id,
        GenerationJob.deleted_at == None,
    ).first()
    if not job:
        raise HTTPException(404, detail="Job não encontrado.")

    job.deleted_at = datetime.utcnow()
    db.commit()
    return StandardResponse(data={
        "id": str(job.id),
        "deleted_at": job.deleted_at.isoformat(),
    })


@router.delete("/cleanup-broken")
def cleanup_broken_jobs(
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """
    Hard deletes jobs where:
    - type is color_variation
    - result is null OR jpg_url is missing OR file does not exist on disk

    Ferramenta de manutenção — hard delete intencional para jobs corrompidos
    (sem arquivo em disco). Não processa jobs com deleted_at (ADR-003).
    """
    upload_dir = os.getenv("UPLOAD_DIR", "/app/examples/uploads")

    jobs = db.query(GenerationJob).filter(
        GenerationJob.type == JobType.color_variation,
        GenerationJob.deleted_at == None,
    ).all()

    deleted = 0
    for job in jobs:
        should_delete = False
        if not job.result:
            should_delete = True
        else:
            try:
                result = json.loads(job.result)
                jpg_url = result.get("jpg_url", "")
                if not jpg_url:
                    should_delete = True
                else:
                    file_path = jpg_url.replace("/static/uploads", upload_dir)
                    if not Path(file_path).exists():
                        should_delete = True
            except Exception:
                should_delete = True

        if should_delete:
            db.delete(job)
            deleted += 1

    db.commit()
    return StandardResponse(data={"deleted": deleted, "message": f"{deleted} jobs corrompidos removidos."})


@router.get("")
def list_jobs(
    product_id: str | None = None,
    type: str | None = None,
    status: str | None = None,
    include_archived: bool = False,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    query = db.query(GenerationJob).filter(
        GenerationJob.deleted_at == None,
    )

    if not include_archived:
        query = query.filter(GenerationJob.is_archived == False)

    if product_id:
        query = query.join(ProductImage).filter(
            ProductImage.product_id == product_id
        )
    if type:
        query = query.filter(GenerationJob.type == type)
    if status:
        query = query.filter(GenerationJob.status == status)

    jobs = query.order_by(GenerationJob.created_at.desc()).limit(200).all()

    products_map = _prefetch_product_names(db, jobs)

    result = []
    for j in jobs:
        pid = str(j.product_image.product_id) if j.product_image else None
        product_name = products_map.get(pid) if pid else None

        result.append({
            "id": str(j.id),
            "type": j.type.value,
            "status": j.status.value,
            "api_used": j.api_used,
            "cost_cents": j.cost_cents,
            "is_archived": j.is_archived,
            "result": json.loads(j.result) if j.result else None,
            "created_at": j.created_at.isoformat(),
            "completed_at": j.completed_at.isoformat() if j.completed_at else None,
            "product_id": pid,
            "product_name": product_name,
            "view": j.product_image.view if j.product_image else None,
        })

    return StandardResponse(data=result)


@router.get("/history")
def get_history(
    product_id: str | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    from app.models import Product, ProductImage

    query = db.query(GenerationJob).filter(
        GenerationJob.deleted_at == None,
    ).order_by(GenerationJob.created_at.desc())

    if product_id:
        query = query.join(ProductImage).filter(
            ProductImage.product_id == product_id
        )

    jobs = query.limit(limit).all()

    products_map = _prefetch_product_names(db, jobs)

    # Montar response sem queries adicionais
    result = []
    for j in jobs:
        pid = str(j.product_image.product_id) if j.product_image else None
        product_name = products_map.get(pid) if pid else None
        job_result = json.loads(j.result) if j.result else {}

        result.append({
            "id": str(j.id),
            "product_id": pid,
            "product_name": product_name,
            "view": j.product_image.view if j.product_image else None,
            "type": j.type.value,
            "status": j.status.value,
            "is_archived": j.is_archived,
            "api_used": j.api_used,
            "model_used": j.model_used,
            "prompt_used": j.prompt_used,
            "input_image_url": j.input_image_url,
            "output_jpg_url": job_result.get("jpg_url"),
            "output_png_url": job_result.get("png_url"),
            "color_hex": job_result.get("color_hex"),
            "cost_cents": j.cost_cents,
            "cost_brl": round((j.cost_cents or 0) * 0.006, 4),
            "tokens_used": j.tokens_used,
            "duration_ms": j.duration_ms,
            "error_message": j.error_message,
            "fallback_reason": j.fallback_reason,
            "method": job_result.get("method"),
            "created_at": j.created_at.isoformat(),
            "completed_at": j.completed_at.isoformat() if j.completed_at else None,
        })

    return StandardResponse(data=result)


@router.patch("/{job_id}/archive")
def archive_job(
    job_id: UUID,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    job = db.query(GenerationJob).filter(
        GenerationJob.id == job_id,
        GenerationJob.deleted_at == None,
    ).first()
    if not job:
        raise HTTPException(404, detail="Job nao encontrado.")
    job.is_archived = True
    db.commit()
    return StandardResponse(data={"job_id": str(job_id), "is_archived": True})


@router.patch("/{job_id}/unarchive")
def unarchive_job(
    job_id: UUID,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    job = db.query(GenerationJob).filter(
        GenerationJob.id == job_id,
        GenerationJob.deleted_at == None,
    ).first()
    if not job:
        raise HTTPException(404, detail="Job nao encontrado.")
    job.is_archived = False
    db.commit()
    return StandardResponse(data={"job_id": str(job_id), "is_archived": False})


@router.get("/export/{product_id}")
def export_product_zip(
    product_id: UUID,
    status: str = "approved",
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    from app.models import Product

    jobs = (
        db.query(GenerationJob)
        .join(ProductImage)
        .filter(
            ProductImage.product_id == product_id,
            GenerationJob.type == JobType.color_variation,
            GenerationJob.is_archived == False,
            GenerationJob.deleted_at == None,
        )
        .all()
    )

    if status != "all":
        jobs = [j for j in jobs if j.status.value == status]

    if not jobs:
        raise HTTPException(404, detail="Nenhuma imagem encontrada para exportar.")

    product = db.query(Product).filter(Product.id == product_id).first()
    product_name = product.name.replace(" ", "_") if product else str(product_id)

    upload_dir = os.getenv("UPLOAD_DIR", "/app/examples/uploads")
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for job in jobs:
            if not job.result:
                continue
            result = json.loads(job.result)
            jpg_url = result.get("jpg_url", "")
            file_path = jpg_url.replace("/static/uploads", upload_dir)

            if not Path(file_path).exists():
                continue

            color = result.get("color_hex", "").replace("#", "")
            view = job.product_image.view or "sem_view"
            short_id = str(job.id)[:6]
            filename = f"{color}_{view}_{short_id}.jpg"
            zf.write(file_path, filename)

    zip_buffer.seek(0)

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={product_name}_export.zip"}
    )


class BulkExportRequest(BaseModel):
    product_ids: list[str]
    status: str = "approved"


@router.post("/export/bulk")
def export_bulk_zip(
    payload: BulkExportRequest,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    from app.models import Product

    zip_buffer = io.BytesIO()
    total_files = 0
    upload_dir = os.getenv("UPLOAD_DIR", "/app/examples/uploads")

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for product_id in payload.product_ids:
            product = db.query(Product).filter(Product.id == product_id).first()
            if not product:
                continue

            folder = product.name.replace(" ", "_")[:30]

            jobs = (
                db.query(GenerationJob)
                .join(ProductImage)
                .filter(
                    ProductImage.product_id == product_id,
                    GenerationJob.type == JobType.color_variation,
                    GenerationJob.is_archived == False,
                    GenerationJob.deleted_at == None,
                )
                .all()
            )

            if payload.status != "all":
                jobs = [j for j in jobs if j.status.value == payload.status]

            for job in jobs:
                if not job.result:
                    continue
                result = json.loads(job.result)
                jpg_url = result.get("jpg_url", "")
                file_path = jpg_url.replace("/static/uploads", upload_dir)

                if not Path(file_path).exists():
                    continue

                color = result.get("color_hex", "").replace("#", "")
                view = job.product_image.view or "sem_view"
                short_id = str(job.id)[:6]
                filename = f"{folder}/{color}_{view}_{short_id}.jpg"
                zf.write(file_path, filename)
                total_files += 1

    if total_files == 0:
        raise HTTPException(404, detail="Nenhuma imagem encontrada para exportar.")

    zip_buffer.seek(0)

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=confexai_export.zip"}
    )


@router.get("/{job_id}")
def get_job(
    job_id: UUID,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    job = db.query(GenerationJob).filter(
        GenerationJob.id == job_id,
        GenerationJob.deleted_at == None,
    ).first()
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
    job = db.query(GenerationJob).filter(
        GenerationJob.id == job_id,
        GenerationJob.deleted_at == None,
    ).first()
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
    job = db.query(GenerationJob).filter(
        GenerationJob.id == job_id,
        GenerationJob.deleted_at == None,
    ).first()
    if not job:
        raise HTTPException(404, detail="Job nao encontrado.")
    if job.status not in (JobStatus.pending_review, JobStatus.done):
        raise HTTPException(409, detail=f"Job nao pode ser rejeitado. Status: {job.status.value}")
    job.status = JobStatus.rejected
    job.rejection_reason = payload.reason
    job.is_archived = True  # auto-archive rejected jobs
    db.commit()
    return StandardResponse(data={
        "job_id": str(job_id),
        "status": "rejected",
        "reason": payload.reason,
    })
