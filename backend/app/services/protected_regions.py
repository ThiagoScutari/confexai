import anthropic
import base64
import json
import logging
import time
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
{{
  "has_protected_regions": boolean,
  "protected_regions": [
    {{
      "type": "estampa" | "bordado" | "aplique" | "outro",
      "description": "brief description in Portuguese",
      "bbox": {{"x": integer, "y": integer, "width": integer, "height": integer}},
      "confidence": float
    }}
  ]
}}

Image dimensions: {width}x{height}px
"""


def detect_protected_regions(image_bytes: bytes) -> dict:
    """
    Usa Claude Vision para detectar regioes protegidas (estampas, bordados).
    Retorna dict com has_protected_regions e lista de regioes.
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
        start_ms = int(time.time() * 1000)

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

        duration_ms = int(time.time() * 1000) - start_ms
        raw = response.content[0].text.strip()
        result = json.loads(raw)
        tokens = response.usage.input_tokens + response.usage.output_tokens
        result["tokens_used"] = tokens
        result["prompt_used"] = prompt
        result["model_used"] = "claude-sonnet-4-20250514"
        result["duration_ms"] = duration_ms
        result["api_log"] = {
            "request_payload": json.dumps({
                "model": "claude-sonnet-4-20250514",
                "prompt_preview": prompt[:200],
                "image_size_bytes": len(image_bytes),
                "max_tokens": 1024,
            }),
            "response_payload": json.dumps({
                "has_protected_regions": result.get("has_protected_regions"),
                "regions_count": len(result.get("protected_regions", [])),
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "duration_ms": duration_ms,
            }),
            "http_status": 200,
        }
        return result

    except json.JSONDecodeError as e:
        logger.error(f"Claude retornou JSON invalido: {e}")
        # Fallback seguro — sem regioes detectadas, sinalizar revisao manual
        return {
            "has_protected_regions": False,
            "protected_regions": [],
            "tokens_used": 0,
            "parse_error": True,
        }
    except Exception as e:
        logger.error(f"Erro na deteccao de regioes protegidas: {e}", exc_info=True)
        raise
