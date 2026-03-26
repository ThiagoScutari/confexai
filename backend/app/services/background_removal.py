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
    Verifica se a imagem ja tem fundo transparente.
    Usado para pular rembg em imagens ja processadas.
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
