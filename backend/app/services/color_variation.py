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
    Gera mascara PNG onde:
    - Branco (255) = area livre para recolorir
    - Preto (0) = regiao protegida, nao alterar
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
    Aplica variacao de cor via Gemini Imagen.
    Retorna dict com resultado e custo.
    """
    import google.generativeai as genai

    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

    img = Image.open(io.BytesIO(image_bytes))
    width, height = img.size

    prompt = COLOR_VARIATION_PROMPT.format(color_hex=target_hex)

    # Preparar imagem e mascara para a API
    image_part = {"mime_type": "image/png", "data": image_bytes}
    mask_bytes = generate_mask((width, height), protected_regions)

    model = genai.GenerativeModel("gemini-2.0-flash-exp")

    # Usar Gemini para edicao de imagem
    response = model.generate_content(
        [prompt, {"mime_type": "image/png", "data": image_bytes}],
        generation_config={"response_mime_type": "image/png"},
    )

    # Extrair bytes da imagem gerada
    result_bytes = response.candidates[0].content.parts[0].inline_data.data

    # Salvar resultado
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(result_bytes)

    # Gerar versao JPG 1200x1200 para plataformas
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
