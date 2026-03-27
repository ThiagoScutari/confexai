import io
import json
import logging
import os
import time
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
    Tenta Gemini primeiro. Se falhar, usa fallback Pillow.
    Registra qual metodo foi usado no resultado.
    """
    try:
        result = _apply_via_gemini(image_bytes, target_hex, protected_regions, output_path)
        result["method"] = "gemini"
        return result
    except Exception as e:
        logger.warning(f"Gemini falhou ({e}), usando fallback Pillow para {target_hex}")
        result = _apply_via_pillow(image_bytes, target_hex, output_path)
        result["method"] = "pillow_fallback"
        result["cost_cents"] = 0  # fallback e gratuito
        return result


def _apply_via_gemini(
    image_bytes: bytes,
    target_hex: str,
    protected_regions: list[dict],
    output_path: Path,
) -> dict:
    """Aplica variacao de cor via Gemini (google-genai SDK)."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

    img = Image.open(io.BytesIO(image_bytes))
    width, height = img.size

    prompt = COLOR_VARIATION_PROMPT.format(color_hex=target_hex)

    start_ms = int(time.time() * 1000)

    response = client.models.generate_content(
        model="gemini-2.5-flash-image",
        contents=[
            types.Part.from_text(text=prompt),
            types.Part.from_bytes(
                data=image_bytes,
                mime_type="image/png",
            ),
        ],
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
        ),
    )

    duration_ms = int(time.time() * 1000) - start_ms

    # Extrair imagem da resposta
    result_bytes = None
    for part in response.candidates[0].content.parts:
        if part.inline_data is not None:
            result_bytes = part.inline_data.data
            break

    if result_bytes is None:
        raise ValueError("Gemini nao retornou imagem na resposta")

    # Salvar resultado e gerar JPG
    result = _save_result(result_bytes, output_path, width, height)
    result["prompt_used"] = prompt
    result["model_used"] = "gemini-2.5-flash-image"
    result["duration_ms"] = duration_ms
    result["api_log"] = {
        "request_payload": json.dumps({
            "model": "gemini-2.5-flash-image",
            "prompt": prompt,
            "image_size_bytes": len(image_bytes),
            "response_modalities": ["IMAGE", "TEXT"],
        }),
        "response_payload": json.dumps({
            "candidates_count": len(response.candidates),
            "has_image": result_bytes is not None,
            "duration_ms": duration_ms,
        }),
        "http_status": 200,
    }
    return result


def _apply_via_pillow(
    image_bytes: bytes,
    target_hex: str,
    output_path: Path,
) -> dict:
    """
    Fallback deterministico: aplica tint de cor via multiplicacao de canal.
    Resultado menos realista mas funcional para MVP.
    """
    start_ms = int(time.time() * 1000)
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    width, height = img.size

    r = int(target_hex[1:3], 16) / 255
    g = int(target_hex[3:5], 16) / 255
    b = int(target_hex[5:7], 16) / 255

    img_array = np.array(img).astype(float)
    # Preservar canal alpha
    alpha = img_array[:, :, 3]
    # Converter para escala de cinza (luminancia)
    gray = 0.299 * img_array[:, :, 0] + 0.587 * img_array[:, :, 1] + 0.114 * img_array[:, :, 2]
    # Aplicar cor alvo mantendo luminancia
    img_array[:, :, 0] = np.clip(gray * r * 2, 0, 255)
    img_array[:, :, 1] = np.clip(gray * g * 2, 0, 255)
    img_array[:, :, 2] = np.clip(gray * b * 2, 0, 255)
    img_array[:, :, 3] = alpha

    result_img = Image.fromarray(img_array.astype(np.uint8))

    # Salvar PNG
    buf = io.BytesIO()
    result_img.save(buf, format="PNG")
    result_bytes = buf.getvalue()

    duration_ms = int(time.time() * 1000) - start_ms
    result = _save_result(result_bytes, output_path, width, height)
    result["prompt_used"] = f"Pillow color tint: {target_hex}"
    result["model_used"] = "pillow_fallback"
    result["duration_ms"] = duration_ms
    result["api_log"] = None
    return result


def _save_result(result_bytes: bytes, output_path: Path, width: int, height: int) -> dict:
    """Salva PNG e gera versao JPG 1200x1200."""
    from app.services.url_helper import path_to_url

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
        "png_url": path_to_url(output_path),
        "jpg_url": path_to_url(jpg_path),
        "resolution": f"{width}x{height}",
        "cost_cents": GEMINI_COST_PER_IMAGE_CENTS,
    }
