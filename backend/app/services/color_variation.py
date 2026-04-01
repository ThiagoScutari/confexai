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


COLOR_VARIATION_PROMPT = """You are editing a product photograph for an e-commerce catalog.

TASK: Change ONLY the fabric color of this exact clothing item to {color_hex}.

CRITICAL CONSTRAINTS — do NOT violate any:
1. This is the SAME garment — preserve every structural detail: seams, buttons, collar, cuffs, pockets, zippers, labels, stitching
2. Preserve the EXACT silhouette, proportions, and pose of the garment
3. Preserve ALL fabric texture: weave pattern, creases, natural folds, wrinkles, shadows, highlights
4. Preserve the EXACT lighting direction and intensity
5. The color {color_hex} must be applied as a fabric dye — not as a color overlay or filter
6. Shadowed areas should be a darker shade of {color_hex}, highlighted areas a lighter shade
7. Do NOT change, add, or remove any design element
8. Do NOT change the image composition, framing, or aspect ratio
9. The background must remain completely transparent (no solid color)
10. Output the image at the highest possible resolution

The result must be indistinguishable from a real product photo of this exact garment in the color {color_hex}."""


def _restore_alpha(original_bytes: bytes, gemini_bytes: bytes) -> bytes:
    """
    Aplica o canal alpha da imagem original sobre o output do Gemini.
    Restaura transparência do fundo e redimensiona para resolução original.
    """
    original = Image.open(io.BytesIO(original_bytes)).convert("RGBA")
    gemini_img = Image.open(io.BytesIO(gemini_bytes)).convert("RGBA")

    # Redimensionar output do Gemini para o tamanho da original
    if gemini_img.size != original.size:
        gemini_img = gemini_img.resize(original.size, Image.LANCZOS)

    # Extrair canal alpha da original e aplicar sobre o resultado
    _, _, _, original_alpha = original.split()
    gemini_img.putalpha(original_alpha)

    buf = io.BytesIO()
    gemini_img.save(buf, format="PNG")
    return buf.getvalue()


def _compute_quality_metrics(original_bytes: bytes, result_bytes: bytes, target_hex: str) -> dict:
    """Calcula métricas de qualidade para o resultado da variação de cor."""
    from PIL import ImageFilter

    original = Image.open(io.BytesIO(original_bytes)).convert("RGBA")
    result = Image.open(io.BytesIO(result_bytes)).convert("RGBA")

    if result.size != original.size:
        result = result.resize(original.size, Image.LANCZOS)

    orig_arr = np.array(original)
    result_arr = np.array(result)

    # Máscara da roupa (alpha > 128)
    mask = orig_arr[:, :, 3] > 128

    if not mask.any():
        return {"edge_correlation": 0.0, "color_distance": 999.0, "quality_warning": True}

    # 1. Correlação de bordas (preservação de estrutura)
    orig_gray = Image.fromarray(
        (0.299 * orig_arr[:, :, 0] + 0.587 * orig_arr[:, :, 1] + 0.114 * orig_arr[:, :, 2]).astype(np.uint8)
    )
    result_gray = Image.fromarray(
        (0.299 * result_arr[:, :, 0] + 0.587 * result_arr[:, :, 1] + 0.114 * result_arr[:, :, 2]).astype(np.uint8)
    )
    orig_edges = np.array(orig_gray.filter(ImageFilter.FIND_EDGES))
    result_edges = np.array(result_gray.filter(ImageFilter.FIND_EDGES))

    oe = orig_edges[mask].astype(float)
    re = result_edges[mask].astype(float)
    edge_correlation = float(np.corrcoef(oe, re)[0, 1]) if oe.std() > 0 and re.std() > 0 else 0.0

    # 2. Precisão de cor (distância euclidiana do target)
    target_r = int(target_hex[1:3], 16)
    target_g = int(target_hex[3:5], 16)
    target_b = int(target_hex[5:7], 16)

    result_r = float(result_arr[:, :, 0][mask].mean())
    result_g = float(result_arr[:, :, 1][mask].mean())
    result_b = float(result_arr[:, :, 2][mask].mean())

    color_distance = ((result_r - target_r) ** 2 + (result_g - target_g) ** 2 + (result_b - target_b) ** 2) ** 0.5

    return {
        "edge_correlation": round(edge_correlation, 4),
        "color_distance": round(color_distance, 1),
        "target_hex": target_hex,
        "result_mean_rgb": [round(result_r), round(result_g), round(result_b)],
        "quality_warning": edge_correlation < 0.40 or color_distance > 100,
    }


def apply_color_variation(
    image_bytes: bytes,
    target_hex: str,
    protected_regions: list[dict],
    output_path: Path,
) -> dict:
    """
    Aplica variação de cor via Gemini (primário) com fallback Pillow LAB.
    ADR-006: usar google-genai SDK com response_modalities
    ADR-007: Pillow fallback automático se Gemini falhar
    """
    try:
        result = _apply_via_gemini(image_bytes, target_hex, protected_regions, output_path)
        result["fallback_reason"] = None
        return result
    except Exception as e:
        logger.warning(f"Gemini falhou para {target_hex}: {e} — ativando Pillow fallback")
        result = _apply_via_pillow(image_bytes, target_hex, output_path)
        result["fallback_reason"] = f"Gemini erro: {str(e)[:200]}"
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
            response_modalities=["IMAGE"],
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

    # Pós-processamento: restaurar alpha e resolução da original
    result_bytes = _restore_alpha(image_bytes, result_bytes)

    # Métricas de qualidade
    quality = _compute_quality_metrics(image_bytes, result_bytes, target_hex)

    # Salvar resultado e gerar JPG
    result = _save_result(result_bytes, output_path, width, height)
    result["color_hex"] = target_hex
    result["method"] = "gemini"
    result["cost_cents"] = GEMINI_COST_PER_IMAGE_CENTS
    result["quality_metrics"] = quality
    result["prompt_used"] = prompt
    result["model_used"] = "gemini-2.5-flash-image"
    result["duration_ms"] = duration_ms
    result["api_log"] = {
        "request_payload": json.dumps({
            "model": "gemini-2.5-flash-image",
            "prompt": prompt,
            "image_size_bytes": len(image_bytes),
            "response_modalities": ["IMAGE"],
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
    Fallback deterministico: aplica cor via transferência no espaço LAB.
    Preserva luminância (sombras/highlights) e troca crominância para a cor alvo.
    """
    from skimage import color as skcolor

    start_ms = int(time.time() * 1000)
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    width, height = img.size
    img_arr = np.array(img).astype(float)
    alpha = img_arr[:, :, 3].copy()

    # Converter RGB para LAB
    rgb_normalized = img_arr[:, :, :3] / 255.0
    lab = skcolor.rgb2lab(rgb_normalized)

    # Cor alvo em LAB
    target_r = int(target_hex[1:3], 16) / 255.0
    target_g = int(target_hex[3:5], 16) / 255.0
    target_b = int(target_hex[5:7], 16) / 255.0
    target_lab = skcolor.rgb2lab(np.array([[[target_r, target_g, target_b]]]))[0, 0]

    # Máscara da roupa (pixels não-transparentes)
    garment_mask = alpha > 128

    if garment_mask.any():
        # Transferir crominância (a, b) do target, preservar luminância relativa
        lab[:, :, 1][garment_mask] = target_lab[1]
        lab[:, :, 2][garment_mask] = target_lab[2]

        # Ajustar luminância proporcionalmente
        orig_L_mean = lab[:, :, 0][garment_mask].mean()
        target_L = target_lab[0]
        if orig_L_mean > 0:
            L_ratio = target_L / orig_L_mean
            lab[:, :, 0][garment_mask] = np.clip(lab[:, :, 0][garment_mask] * L_ratio, 0, 100)

    # Converter de volta para RGB
    rgb_result = np.clip(skcolor.lab2rgb(lab) * 255, 0, 255).astype(np.uint8)

    # Restaurar alpha
    result_arr = np.dstack([rgb_result, alpha.astype(np.uint8)])
    result_img = Image.fromarray(result_arr)

    # Salvar PNG
    buf = io.BytesIO()
    result_img.save(buf, format="PNG")
    result_bytes = buf.getvalue()

    duration_ms = int(time.time() * 1000) - start_ms
    result = _save_result(result_bytes, output_path, width, height)
    result["color_hex"] = target_hex
    result["method"] = "pillow_fallback"
    result["cost_cents"] = 0
    result["prompt_used"] = f"Pillow LAB color transfer: {target_hex}"
    result["model_used"] = "pillow_fallback_lab"
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
    }
