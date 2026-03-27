import os
import logging
from uuid import UUID
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session
from PIL import Image as PILImage
import io

from app.database import get_db
from app.auth import get_current_user
from app.models import Product, ProductImage, GenerationJob, JobType, JobStatus
from app.services.url_helper import path_to_url
from app.schemas.images import ImageResponse
from app.schemas.common import StandardResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/products", tags=["images"])

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./uploads"))
MAX_IMAGE_SIZE_MB = int(os.getenv("MAX_IMAGE_SIZE_MB", 20))
ALLOWED_TYPES = {"image/jpeg", "image/png"}
MIN_RESOLUTION = 500


@router.post(
    "/{product_id}/images/upload",
    response_model=StandardResponse[ImageResponse],
    status_code=201,
)
async def upload_image(
    product_id: UUID,
    file: UploadFile = File(...),
    view: str | None = Query(None, pattern="^(frente|costas|lat_direita|lat_esquerda)$"),
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    # Validar produto
    product = db.query(Product).filter(
        Product.id == product_id, Product.is_active == True
    ).first()
    if not product:
        raise HTTPException(404, detail="Produto nao encontrado.")

    # Validar tipo de arquivo
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(422, detail="Formato invalido. Use JPG ou PNG.")

    # Ler conteudo
    content = await file.read()

    # Validar tamanho
    size_mb = len(content) / (1024 * 1024)
    if size_mb > MAX_IMAGE_SIZE_MB:
        raise HTTPException(422, detail=f"Arquivo muito grande. Maximo: {MAX_IMAGE_SIZE_MB}MB.")

    # Validar resolucao minima
    try:
        img = PILImage.open(io.BytesIO(content))
        w, h = img.size
        if w < MIN_RESOLUTION or h < MIN_RESOLUTION:
            raise HTTPException(
                422,
                detail=f"Resolucao minima: {MIN_RESOLUTION}x{MIN_RESOLUTION}px. "
                       f"Recebido: {w}x{h}px."
            )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(422, detail="Arquivo de imagem invalido ou corrompido.")

    # Salvar arquivo
    product_dir = UPLOAD_DIR / str(product_id)
    product_dir.mkdir(parents=True, exist_ok=True)
    file_path = product_dir / f"original{Path(file.filename).suffix}"
    file_path.write_bytes(content)

    # Registrar no banco
    try:
        image = ProductImage(
            product_id=product_id,
            type="original",
            view=view,
            original_url=str(file_path),
        )
        db.add(image)
        db.commit()
        db.refresh(image)

        response_data = ImageResponse(
            id=image.id,
            product_id=image.product_id,
            type=image.type,
            original_url=image.original_url,
            processed_url=image.processed_url,
            public_url=path_to_url(image.original_url),
            view=image.view,
            status="uploaded",
            created_at=image.created_at,
        )
        return StandardResponse(data=response_data)
    except Exception as e:
        logger.error(f"Erro ao registrar imagem: {e}", exc_info=True)
        raise HTTPException(500, detail="Erro interno do servidor.")


@router.post("/{product_id}/images/{image_id}/remove-background", status_code=202)
async def remove_image_background(
    product_id: UUID,
    image_id: UUID,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    from app.services.background_removal import (
        remove_background as svc_remove_bg,
        image_already_transparent,
    )
    import json

    image = db.query(ProductImage).filter(
        ProductImage.id == image_id,
        ProductImage.product_id == product_id,
        ProductImage.is_active == True,
    ).first()
    if not image:
        raise HTTPException(404, detail="Imagem nao encontrada.")

    try:
        with open(image.original_url, "rb") as f:
            image_bytes = f.read()

        # Verificar se ja e transparente
        already_transparent = image_already_transparent(image_bytes)
        if already_transparent:
            image.processed_url = image.original_url  # ja processada
            db.commit()
            job = GenerationJob(
                product_image_id=image_id,
                type=JobType.background_removal,
                status=JobStatus.done,
                api_used="skip_already_transparent",
                cost_cents=0,
                result=json.dumps({"skipped": True, "reason": "already_transparent"}),
            )
            db.add(job)
            db.commit()
            db.refresh(job)
            return StandardResponse(data={"job_id": str(job.id), "status": "done", "skipped": True})

        # Processar com rembg
        png_bytes, confidence = svc_remove_bg(image_bytes)

        # Salvar PNG processado
        original_path = Path(image.original_url)
        processed_path = original_path.parent / f"{original_path.stem}_nobg.png"
        processed_path.write_bytes(png_bytes)
        image.processed_url = str(processed_path)
        db.commit()

        job = GenerationJob(
            product_image_id=image_id,
            type=JobType.background_removal,
            status=JobStatus.done,
            api_used="rembg",
            cost_cents=0,
            result=json.dumps({"confidence": round(confidence, 3), "skipped": False}),
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        return StandardResponse(data={
            "job_id": str(job.id),
            "status": "done",
            "confidence": round(confidence, 3),
            "processed_url": str(processed_path),
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro na remocao de fundo: {e}", exc_info=True)
        raise HTTPException(500, detail="Erro interno do servidor.")
