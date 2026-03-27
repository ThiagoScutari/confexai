# PRD — Sprint 02: Remoção de Fundo e Variação de Cor

**Status:** Aprovação Pendente  
**Origem:** Feature — primeiro módulo de IA do ConfexAI  
**Data:** 2026-03-26  
**Objetivo:** Processar as imagens de `examples/` e gerar variações de cor nas 3 cores HEX fornecidas, com detecção de regiões protegidas e aprovação humana antes do export.

---

## Contexto dos Arquivos de Teste

```
examples/
├── cores/
│   ├── #696980.png   → tom cinza-azulado
│   ├── #978b7b.png   → tom bege-rosado
│   └── #9e987d.png   → tom cáqui-esverdeado
└── roupa/
    ├── frente.png        → PNG transparente ✅
    ├── costas.png        → PNG transparente ✅
    ├── lat_direita.png   → PNG transparente ✅
    └── lat_esquerda.png  → PNG transparente ✅
```

**Observações que impactam o sprint:**
- Imagens já sem fundo — o endpoint de remoção de fundo deve existir mas pode ser pulado no fluxo de teste
- Peça lisa sem estampa/bordado — detecção de regiões protegidas retornará `has_protected_regions: false`
- 4 ângulos por produto — o modelo `ProductImage` precisa do campo `view` para diferenciar frente/costas/laterais
- Cores identificadas pelo nome do arquivo HEX — o sistema lê o HEX diretamente do nome

---

## Sumário Executivo

| ID | Tipo | Descrição | Esforço |
|---|---|---|---|
| S02-01 | feat | Campo `view` em `ProductImage` + migration | Pequeno |
| S02-02 | feat | Endpoint de remoção de fundo (rembg) | Médio |
| S02-03 | feat | Job de detecção de regiões protegidas (Claude Vision) | Médio |
| S02-04 | feat | Job de variação de cor (Gemini Imagen) | Médio |
| S02-05 | feat | Endpoints de aprovação e rejeição de jobs | Pequeno |
| S02-06 | test | Testes para todos os itens acima (mocks de API) | Médio |

**Critério de aceite:** Subir as 4 imagens de `examples/roupa/`, rodar detecção (retorna `has_protected_regions: false`), gerar variação nas 3 cores de `examples/cores/`, aprovar resultados — tudo via API, testes verdes.

---

## S02-01 — Campo `view` em ProductImage + Migration

### Motivação
Um produto tem múltiplos ângulos (frente, costas, lat_direita, lat_esquerda).
O modelo atual não diferencia ângulos — todos seriam `type: "original"` sem distinção.

### Alteração em `backend/app/models.py`

```python
# Adicionar campo view em ProductImage
class ProductImage(Base):
    __tablename__ = "product_images"
    # ... campos existentes ...
    view = Column(String(30), nullable=True)  # frente | costas | lat_direita | lat_esquerda | null
```

### Alteração em `backend/app/schemas/images.py`

```python
from typing import Literal

ImageView = Literal["frente", "costas", "lat_direita", "lat_esquerda"] | None

class ImageResponse(BaseModel):
    # ... campos existentes ...
    view: ImageView = None
```

### Alteração em `backend/app/api/images.py`

Upload deve aceitar `view` como query param opcional:

```python
@router.post("/{product_id}/images/upload", ...)
async def upload_image(
    product_id: UUID,
    file: UploadFile = File(...),
    view: str | None = Query(None, pattern="^(frente|costas|lat_direita|lat_esquerda)$"),
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    # ... salvar arquivo ...
    image = ProductImage(
        product_id=product_id,
        type="original",
        view=view,            # ← novo
        original_url=str(file_path),
    )
```

### `backend/app/migrations/migrate_sprint_02.py`

```python
"""
Migration Sprint 02 — Adiciona campo view em product_images.
Idempotente.
"""
import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://confexai:confexai@localhost/confexai_db")
engine = create_engine(DATABASE_URL)


def migrate():
    with engine.begin() as conn:
        result = conn.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name='product_images' AND column_name='view'
        """))
        if not result.fetchone():
            conn.execute(text(
                "ALTER TABLE product_images ADD COLUMN view VARCHAR(30) NULL"
            ))
            print("✅ Campo 'view' adicionado em product_images.")
        else:
            print("✅ Campo 'view' já existe.")


if __name__ == "__main__":
    migrate()
```

---

## S02-02 — Endpoint de Remoção de Fundo

### `backend/app/services/background_removal.py`

```python
import io
import logging
from PIL import Image

logger = logging.getLogger(__name__)

CONFIDENCE_THRESHOLD = 0.85


def remove_background(image_bytes: bytes) -> tuple[bytes, float]:
    """
    Remove fundo com rembg.
    Retorna (png_bytes, confidence_score).
    """
    try:
        from rembg import remove
        output = remove(image_bytes)
        confidence = _calculate_confidence(output)
        logger.info(f"rembg confidence: {confidence:.2f}")
        return output, confidence
    except Exception as e:
        logger.error(f"Erro no rembg: {e}", exc_info=True)
        raise


def _calculate_confidence(png_bytes: bytes) -> float:
    img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    alpha = list(img.split()[3].getdata())
    total = len(alpha)
    if total == 0:
        return 0.0
    extreme = sum(1 for p in alpha if p < 10 or p > 245)
    return extreme / total


def image_already_transparent(png_bytes: bytes) -> bool:
    """
    Verifica se a imagem já tem fundo transparente.
    Usado para pular rembg em imagens já processadas.
    """
    try:
        img = Image.open(io.BytesIO(png_bytes))
        if img.mode != "RGBA":
            return False
        alpha = list(img.split()[3].getdata())
        transparent_pixels = sum(1 for p in alpha if p < 10)
        return transparent_pixels > (len(alpha) * 0.05)  # >5% de pixels transparentes
    except Exception:
        return False
```

### Endpoint em `backend/app/api/images.py` — adicionar:

```python
@router.post("/{product_id}/images/{image_id}/remove-background", status_code=202)
async def remove_background(
    product_id: UUID,
    image_id: UUID,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    from app.services.background_removal import (
        remove_background as svc_remove_bg,
        image_already_transparent,
    )
    from app.models import GenerationJob, JobType, JobStatus
    import json

    image = db.query(ProductImage).filter(
        ProductImage.id == image_id,
        ProductImage.product_id == product_id,
        ProductImage.is_active == True,
    ).first()
    if not image:
        raise HTTPException(404, detail="Imagem não encontrada.")

    try:
        with open(image.original_url, "rb") as f:
            image_bytes = f.read()

        # Verificar se já é transparente
        already_transparent = image_already_transparent(image_bytes)
        if already_transparent:
            image.processed_url = image.original_url  # já processada
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
        from pathlib import Path
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
        logger.error(f"Erro na remoção de fundo: {e}", exc_info=True)
        raise HTTPException(500, detail="Erro interno do servidor.")
```

---

## S02-03 — Job de Detecção de Regiões Protegidas (Claude Vision)

### `backend/app/services/protected_regions.py`

```python
import anthropic
import base64
import json
import logging
from PIL import Image
import io

logger = logging.getLogger(__name__)

DETECTION_PROMPT = """
Analyze this clothing item image and identify ALL regions that should be
PROTECTED from color changes. These are decorative elements with their own
independent colors that should NOT change when the garment base color changes.

Protected region types to detect:
- Prints/Estampas: floral, geometric, abstract, character prints
- Embroidery/Bordados: stitched decorations, logos, patterns
- Patches/Apliques: sewn-on decorative elements
- Contrasting decorative elements: decorative buttons, ribbons, bows in accent colors

DO NOT mark as protected:
- The main fabric area
- Functional buttons, zippers that match the garment
- Seams and stitching that match the garment color
- Shadows and folds

Return ONLY valid JSON, no markdown, no explanation:
{
  "has_protected_regions": boolean,
  "protected_regions": [
    {
      "type": "estampa" | "bordado" | "aplique" | "outro",
      "description": "brief description in Portuguese",
      "bbox": {"x": integer, "y": integer, "width": integer, "height": integer},
      "confidence": float
    }
  ]
}

Image dimensions: {width}x{height}px
"""


def detect_protected_regions(image_bytes: bytes) -> dict:
    """
    Usa Claude Vision para detectar regiões protegidas (estampas, bordados).
    Retorna dict com has_protected_regions e lista de regiões.
    """
    img = Image.open(io.BytesIO(image_bytes))
    width, height = img.size

    client = anthropic.Anthropic()
    image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")

    # Detectar media type
    fmt = img.format or "PNG"
    media_type_map = {"PNG": "image/png", "JPEG": "image/jpeg", "JPG": "image/jpeg"}
    media_type = media_type_map.get(fmt.upper(), "image/png")

    prompt = DETECTION_PROMPT.format(width=width, height=height)

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_b64,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }],
        )
        raw = response.content[0].text.strip()
        result = json.loads(raw)
        tokens = response.usage.input_tokens + response.usage.output_tokens
        return {**result, "tokens_used": tokens}

    except json.JSONDecodeError as e:
        logger.error(f"Claude retornou JSON inválido: {e}")
        # Fallback seguro — sem regiões detectadas, sinalizar revisão manual
        return {
            "has_protected_regions": False,
            "protected_regions": [],
            "tokens_used": 0,
            "parse_error": True,
        }
    except Exception as e:
        logger.error(f"Erro na detecção de regiões protegidas: {e}", exc_info=True)
        raise
```

### Endpoint em `backend/app/api/jobs.py` — criar arquivo:

```python
import json
import logging
import os
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
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
    Dispara detecção de regiões protegidas em uma imagem via Claude Vision.
    payload: { "product_image_id": "uuid" }
    """
    from app.services.protected_regions import detect_protected_regions as svc_detect
    from datetime import datetime

    image_id = payload.get("product_image_id")
    if not image_id:
        raise HTTPException(422, detail="product_image_id é obrigatório.")

    image = db.query(ProductImage).filter(
        ProductImage.id == image_id,
        ProductImage.is_active == True,
    ).first()
    if not image:
        raise HTTPException(404, detail="Imagem não encontrada.")

    # Usar processed_url se disponível (fundo removido), senão original
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
        logger.error(f"Falha na detecção de regiões: {e}", exc_info=True)
        raise HTTPException(500, detail="Erro interno do servidor.")
```

---

## S02-04 — Job de Variação de Cor (Gemini Imagen)

### `backend/app/services/color_variation.py`

```python
import io
import json
import logging
import os
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)

GEMINI_COST_PER_IMAGE_CENTS = 3  # ~$0.03 por imagem gerada


def generate_mask(image_size: tuple[int, int], protected_regions: list[dict]) -> bytes:
    """
    Gera máscara PNG onde:
    - Branco (255) = área livre para recolorir
    - Preto (0) = região protegida, não alterar
    """
    mask = Image.new("L", image_size, 255)
    draw = ImageDraw.Draw(mask)
    for region in protected_regions:
        bbox = region["bbox"]
        feather = 4
        x1 = max(0, bbox["x"] - feather)
        y1 = max(0, bbox["y"] - feather)
        x2 = min(image_size[0], bbox["x"] + bbox["width"] + feather)
        y2 = min(image_size[1], bbox["y"] + bbox["height"] + feather)
        draw.rectangle([x1, y1, x2, y2], fill=0)
    buf = io.BytesIO()
    mask.save(buf, format="PNG")
    return buf.getvalue()


COLOR_VARIATION_PROMPT = """
Recolor this clothing item to the color {color_hex}.

Rules:
- Apply the new color uniformly to the entire garment fabric
- Preserve ALL fabric texture, weave pattern, natural folds, and shadows
- Maintain realistic fabric shading and highlights appropriate for this color
- Keep the result looking like a real product photograph, not an illustration
- Do NOT add any new design elements
- Do NOT change the garment shape or silhouette
- The background must remain fully transparent
"""


def apply_color_variation(
    image_bytes: bytes,
    target_hex: str,
    protected_regions: list[dict],
    output_path: Path,
) -> dict:
    """
    Aplica variação de cor via Gemini Imagen.
    Retorna dict com resultado e custo.
    """
    import google.generativeai as genai

    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

    img = Image.open(io.BytesIO(image_bytes))
    width, height = img.size

    prompt = COLOR_VARIATION_PROMPT.format(color_hex=target_hex)

    # Preparar imagem e máscara para a API
    image_part = {"mime_type": "image/png", "data": image_bytes}
    mask_bytes = generate_mask((width, height), protected_regions)

    model = genai.GenerativeModel("gemini-2.0-flash-exp")

    # Usar Gemini para edição de imagem
    response = model.generate_content(
        [prompt, {"mime_type": "image/png", "data": image_bytes}],
        generation_config={"response_mime_type": "image/png"},
    )

    # Extrair bytes da imagem gerada
    result_bytes = response.candidates[0].content.parts[0].inline_data.data

    # Salvar resultado
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(result_bytes)

    # Gerar versão JPG 1200x1200 para plataformas
    jpg_path = output_path.with_suffix(".jpg")
    result_img = Image.open(io.BytesIO(result_bytes)).convert("RGB")
    result_img.thumbnail((1200, 1200), Image.LANCZOS)
    canvas = Image.new("RGB", (1200, 1200), (255, 255, 255))
    offset = ((1200 - result_img.width) // 2, (1200 - result_img.height) // 2)
    canvas.paste(result_img, offset)
    canvas.save(jpg_path, format="JPEG", quality=92)

    return {
        "png_url": str(output_path),
        "jpg_url": str(jpg_path),
        "resolution": f"{width}x{height}",
        "cost_cents": GEMINI_COST_PER_IMAGE_CENTS,
    }
```

### Adicionar endpoint em `backend/app/api/jobs.py`:

```python
from pydantic import BaseModel

class ColorVariationRequest(BaseModel):
    product_image_id: str
    target_colors: list[str]          # lista de HEX: ["#696980", "#978b7b"]
    protected_regions: list[dict] = [] # vindo do job de detecção


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
        raise HTTPException(404, detail="Imagem não encontrada.")

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

            job.status = JobStatus.pending_review
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
            })

        except Exception as e:
            job.status = JobStatus.failed
            job.error_message = str(e)
            db.commit()
            logger.error(f"Falha na variação de cor {color_hex}: {e}", exc_info=True)
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
```

---

## S02-05 — Endpoints de Aprovação e Rejeição

### Adicionar em `backend/app/api/jobs.py`:

```python
class RejectRequest(BaseModel):
    reason: str


@router.get("/{job_id}")
def get_job(
    job_id: UUID,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    job = db.query(GenerationJob).filter(GenerationJob.id == job_id).first()
    if not job:
        raise HTTPException(404, detail="Job não encontrado.")
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
        raise HTTPException(404, detail="Job não encontrado.")
    if job.status != JobStatus.pending_review:
        raise HTTPException(409, detail=f"Job não está em revisão. Status atual: {job.status.value}")
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
        raise HTTPException(404, detail="Job não encontrado.")
    if job.status not in (JobStatus.pending_review, JobStatus.done):
        raise HTTPException(409, detail=f"Job não pode ser rejeitado. Status: {job.status.value}")
    job.status = JobStatus.rejected
    job.rejection_reason = payload.reason
    db.commit()
    return StandardResponse(data={
        "job_id": str(job_id),
        "status": "rejected",
        "reason": payload.reason,
    })
```

### Registrar router em `backend/app/main.py`:

```python
from app.api import health, auth, products, images, jobs  # ← adicionar jobs

app.include_router(jobs.router)  # ← adicionar linha
```

---

## S02-06 — Testes (todos com mocks de API)

### `backend/tests/test_background_removal.py`

```python
from unittest.mock import patch, MagicMock
import io
from PIL import Image


def _png_transparent() -> bytes:
    img = Image.new("RGBA", (600, 600), (0, 0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _png_opaque() -> bytes:
    img = Image.new("RGBA", (600, 600), (200, 150, 100, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_remover_fundo_imagem_ja_transparente_retorna_skip(
    client, auth_headers, sample_product, tmp_path
):
    # Upload imagem transparente
    upload = client.post(
        f"/api/v1/products/{sample_product.id}/images/upload",
        files={"file": ("frente.png", _png_transparent(), "image/png")},
        params={"view": "frente"},
        headers=auth_headers,
    )
    assert upload.status_code == 201
    image_id = upload.json()["data"]["id"]

    response = client.post(
        f"/api/v1/products/{sample_product.id}/images/{image_id}/remove-background",
        headers=auth_headers,
    )
    assert response.status_code == 202
    data = response.json()["data"]
    assert data["skipped"] is True
    assert data["status"] == "done"


def test_remover_fundo_imagem_opaca_chama_rembg(
    client, auth_headers, sample_product
):
    upload = client.post(
        f"/api/v1/products/{sample_product.id}/images/upload",
        files={"file": ("frente.png", _png_opaque(), "image/png")},
        headers=auth_headers,
    )
    image_id = upload.json()["data"]["id"]

    with patch("app.api.images.svc_remove_bg") as mock_rembg:
        mock_rembg.return_value = (_png_transparent(), 0.92)
        response = client.post(
            f"/api/v1/products/{sample_product.id}/images/{image_id}/remove-background",
            headers=auth_headers,
        )
    assert response.status_code == 202
    assert response.json()["data"]["confidence"] == 0.92


def test_upload_com_view_registra_campo(client, auth_headers, sample_product):
    response = client.post(
        f"/api/v1/products/{sample_product.id}/images/upload",
        files={"file": ("costas.png", _png_transparent(), "image/png")},
        params={"view": "costas"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    assert response.json()["data"]["view"] == "costas"


def test_upload_view_invalido_retorna_422(client, auth_headers, sample_product):
    response = client.post(
        f"/api/v1/products/{sample_product.id}/images/upload",
        files={"file": ("x.png", _png_transparent(), "image/png")},
        params={"view": "diagonal"},
        headers=auth_headers,
    )
    assert response.status_code == 422
```

### `backend/tests/test_protected_regions.py`

```python
from unittest.mock import patch, MagicMock
import json
import io
from PIL import Image


def _sample_png() -> bytes:
    img = Image.new("RGBA", (600, 600), (150, 100, 80, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


MOCK_RESULT_SEM_REGIOES = {
    "has_protected_regions": False,
    "protected_regions": [],
    "tokens_used": 320,
}

MOCK_RESULT_COM_REGIOES = {
    "has_protected_regions": True,
    "protected_regions": [{
        "type": "estampa",
        "description": "estampa floral no centro",
        "bbox": {"x": 100, "y": 80, "width": 200, "height": 180},
        "confidence": 0.91,
    }],
    "tokens_used": 480,
}


def test_detectar_regioes_peca_lisa_retorna_false(client, auth_headers, sample_product):
    upload = client.post(
        f"/api/v1/products/{sample_product.id}/images/upload",
        files={"file": ("frente.png", _sample_png(), "image/png")},
        headers=auth_headers,
    )
    image_id = upload.json()["data"]["id"]

    with patch("app.api.jobs.svc_detect") as mock_detect:
        mock_detect.return_value = MOCK_RESULT_SEM_REGIOES
        response = client.post(
            "/api/v1/jobs/detect-protected-regions",
            json={"product_image_id": image_id},
            headers=auth_headers,
        )

    assert response.status_code == 202
    data = response.json()["data"]
    assert data["has_protected_regions"] is False
    assert data["regions_count"] == 0
    assert data["cost_cents"] >= 0


def test_detectar_regioes_peca_com_estampa_retorna_true(client, auth_headers, sample_product):
    upload = client.post(
        f"/api/v1/products/{sample_product.id}/images/upload",
        files={"file": ("frente.png", _sample_png(), "image/png")},
        headers=auth_headers,
    )
    image_id = upload.json()["data"]["id"]

    with patch("app.api.jobs.svc_detect") as mock_detect:
        mock_detect.return_value = MOCK_RESULT_COM_REGIOES
        response = client.post(
            "/api/v1/jobs/detect-protected-regions",
            json={"product_image_id": image_id},
            headers=auth_headers,
        )

    assert response.status_code == 202
    assert response.json()["data"]["has_protected_regions"] is True
    assert response.json()["data"]["regions_count"] == 1


def test_detectar_regioes_sem_image_id_retorna_422(client, auth_headers):
    response = client.post(
        "/api/v1/jobs/detect-protected-regions",
        json={},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_detectar_regioes_sem_token_retorna_401(client):
    response = client.post("/api/v1/jobs/detect-protected-regions", json={})
    assert response.status_code == 401
```

### `backend/tests/test_color_variation.py`

```python
from unittest.mock import patch, MagicMock
import io
from PIL import Image


def _sample_png() -> bytes:
    img = Image.new("RGBA", (600, 600), (150, 100, 80, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


MOCK_COLOR_RESULT = {
    "png_url": "/tmp/color_696980_frente.png",
    "jpg_url": "/tmp/color_696980_frente.jpg",
    "resolution": "600x600",
    "cost_cents": 3,
}


def test_gerar_variacao_cor_retorna_202(client, auth_headers, sample_product):
    upload = client.post(
        f"/api/v1/products/{sample_product.id}/images/upload",
        files={"file": ("frente.png", _sample_png(), "image/png")},
        params={"view": "frente"},
        headers=auth_headers,
    )
    image_id = upload.json()["data"]["id"]

    with patch("app.api.jobs.apply_color_variation") as mock_cv:
        mock_cv.return_value = MOCK_COLOR_RESULT
        response = client.post(
            "/api/v1/jobs/color-variation",
            json={
                "product_image_id": image_id,
                "target_colors": ["#696980"],
                "protected_regions": [],
            },
            headers=auth_headers,
        )

    assert response.status_code == 202
    results = response.json()["data"]["results"]
    assert len(results) == 1
    assert results[0]["color_hex"] == "#696980"
    assert results[0]["status"] == "pending_review"


def test_gerar_variacao_multiplas_cores(client, auth_headers, sample_product):
    upload = client.post(
        f"/api/v1/products/{sample_product.id}/images/upload",
        files={"file": ("frente.png", _sample_png(), "image/png")},
        headers=auth_headers,
    )
    image_id = upload.json()["data"]["id"]

    with patch("app.api.jobs.apply_color_variation") as mock_cv:
        mock_cv.return_value = {**MOCK_COLOR_RESULT, "cost_cents": 3}
        response = client.post(
            "/api/v1/jobs/color-variation",
            json={
                "product_image_id": image_id,
                "target_colors": ["#696980", "#978b7b", "#9e987d"],
                "protected_regions": [],
            },
            headers=auth_headers,
        )

    assert response.status_code == 202
    data = response.json()["data"]
    assert len(data["results"]) == 3
    assert data["total_cost_cents"] == 9


def test_gerar_variacao_sem_token_retorna_401(client):
    response = client.post("/api/v1/jobs/color-variation", json={})
    assert response.status_code == 401
```

### `backend/tests/test_job_approval.py`

```python
def test_aprovar_job_pending_review(client, auth_headers, sample_job_pending_review):
    response = client.post(
        f"/api/v1/jobs/{sample_job_pending_review.id}/approve",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "approved"


def test_aprovar_job_que_nao_esta_em_revisao_retorna_409(client, auth_headers, sample_job_done):
    response = client.post(
        f"/api/v1/jobs/{sample_job_done.id}/approve",
        headers=auth_headers,
    )
    assert response.status_code == 409


def test_rejeitar_job_registra_motivo(client, auth_headers, sample_job_pending_review):
    response = client.post(
        f"/api/v1/jobs/{sample_job_pending_review.id}/reject",
        json={"reason": "cor ficou muito escura"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "rejected"


def test_buscar_job_por_id(client, auth_headers, sample_job_pending_review):
    response = client.get(
        f"/api/v1/jobs/{sample_job_pending_review.id}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert "status" in response.json()["data"]


def test_aprovar_sem_token_retorna_401(client, sample_job_pending_review):
    response = client.post(f"/api/v1/jobs/{sample_job_pending_review.id}/approve")
    assert response.status_code == 401
```

> **Nota:** adicionar fixtures `sample_job_pending_review` e `sample_job_done`
> no `conftest.py` — criando `GenerationJob` diretamente no banco de teste.

---

## Ordem de Execução

```
S02-01 → S02-02 → S02-03 → S02-04 → S02-05 → S02-06
```

Rodar migration antes dos testes:
```bash
docker compose exec api python backend/app/migrations/migrate_sprint_02.py
```

---

## Commits Atômicos

```
feat(db): add view field to product_images and sprint 02 migration [S02-01]
feat(images): add background removal endpoint with rembg and transparency detection [S02-02]
feat(jobs): add protected region detection endpoint via Claude Vision [S02-03]
feat(jobs): add color variation endpoint via Gemini Imagen [S02-04]
feat(jobs): add job approval and rejection endpoints [S02-05]
test(sprint02): add full test suite with API mocks — target 0 failed [S02-06]
```

---

## Critérios de Aceite

- [ ] Migration S02 roda sem erros
- [ ] Upload de `examples/roupa/frente.png` com `?view=frente` funciona
- [ ] Endpoint de remoção de fundo detecta transparência e retorna `skipped: true`
- [ ] Detecção de regiões protegidas retorna `has_protected_regions: false` para a peça lisa
- [ ] Variação de cor nas 3 cores de `examples/cores/` gera jobs com `status: pending_review`
- [ ] Aprovação e rejeição de jobs funcionam corretamente
- [ ] `pytest backend/tests/ -v` → **todos os testes passam, 0 falhas**
