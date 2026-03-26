import os
import logging
from uuid import UUID
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from PIL import Image as PILImage
import io

from app.database import get_db
from app.auth import get_current_user
from app.models import Product, ProductImage
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
            status="uploaded",
            created_at=image.created_at,
        )
        return StandardResponse(data=response_data)
    except Exception as e:
        logger.error(f"Erro ao registrar imagem: {e}", exc_info=True)
        raise HTTPException(500, detail="Erro interno do servidor.")
