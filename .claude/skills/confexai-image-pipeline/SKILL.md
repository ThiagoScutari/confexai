---
name: confexai-image-pipeline
description: >
  Padrões técnicos do pipeline de imagens do ConfexAI. Use esta SKILL sempre
  que for implementar ou revisar código relacionado a: remoção de fundo,
  detecção de regiões protegidas (estampas/bordados), variação de cor,
  composição de fundo alternativo, ou qualquer operação de processamento de
  imagem. Define os fluxos exatos, prompts para Claude Vision, parâmetros
  para Gemini Imagen, e critérios de qualidade. Consulte antes de qualquer
  implementação de processamento de imagem.
---

# ConfexAI — Pipeline de Imagens

## Visão Geral do Pipeline

```
[Upload JPG/PNG]
      ↓
[1. Remoção de Fundo] → PNG transparente (peça isolada)
      ↓
[2. Detecção de Regiões Protegidas] → máscara + revisão humana
      ↓
      ├──→ [3a. Variação de Cor] → PNG por cor (respeitando máscara)
      ├──→ [3b. Fundo Alternativo] → JPG composição final
      └──→ [3c. Análise para SEO] → dados estruturados → descrição
      ↓
[4. Export padronizado] → JPG 1200×1200 + PNG transparente
```

---

## Etapa 1 — Remoção de Fundo

### Motor primário: rembg (local)

```python
from rembg import remove
from PIL import Image
import io

def remove_background(image_bytes: bytes) -> tuple[bytes, float]:
    """
    Remove fundo da imagem.
    Retorna (png_bytes, confidence_score).
    confidence_score entre 0.0 e 1.0.
    """
    output = remove(image_bytes)
    img = Image.open(io.BytesIO(output)).convert("RGBA")
    
    # Calcular score de confiança baseado em pixels alpha
    alpha = img.split()[3]
    alpha_array = list(alpha.getdata())
    
    # Pixels totalmente transparentes ou totalmente opacos = bom resultado
    extreme_pixels = sum(1 for p in alpha_array if p < 10 or p > 245)
    confidence = extreme_pixels / len(alpha_array)
    
    return output, confidence
```

**Threshold de confiança:** `0.85`  
Se `confidence < 0.85` → acionar fallback Gemini.

### Fallback: Gemini Vision

```python
GEMINI_BACKGROUND_REMOVAL_PROMPT = """
You are a precise image editing assistant.
Remove the background from this clothing item image.
- Keep ONLY the garment
- Make background fully transparent (RGBA)
- Preserve all fabric details, shadows, and folds
- Do not alter the garment colors or texture
Return the edited image as PNG with transparency.
"""
```

### Pós-processamento obrigatório

Após remoção de fundo (qualquer motor):
1. Converter para RGBA se necessário
2. Aplicar suavização nas bordas (feather 2px)
3. Recortar canvas para bounding box da peça + 5% de padding
4. Salvar como PNG-24 com transparência

---

## Etapa 2 — Detecção de Regiões Protegidas

> ⚠️ **Regra crítica:** estampas, bordados, patches e aplicações decorativas
> nunca mudam de cor. Esta etapa é obrigatória antes de qualquer variação de cor.

### Prompt para Claude Vision

```python
PROTECTED_REGION_DETECTION_PROMPT = """
Analyze this clothing item image and identify ALL regions that should be 
PROTECTED from color changes. These are decorative elements that have their 
own independent colors and should NOT change when the garment base color changes.

Protected region types to detect:
- Prints/Estampas: floral, geometric, abstract, character prints
- Embroidery/Bordados: stitched decorations, logos, patterns
- Patches/Apliques: sewn-on decorative elements
- Contrasting decorative elements: decorative buttons (NOT functional ones), 
  ribbons, bows, trims in accent colors

DO NOT mark as protected:
- The main fabric/garment area
- Functional buttons, zippers (unless decorative with distinct color)
- Seams and stitching that match the garment color
- Shadows and folds

Return ONLY valid JSON, no markdown, no explanation:
{
  "has_protected_regions": boolean,
  "protected_regions": [
    {
      "type": "estampa" | "bordado" | "aplique" | "outro",
      "description": "brief description in Portuguese",
      "bbox": {
        "x": integer (pixels from left),
        "y": integer (pixels from top),
        "width": integer,
        "height": integer
      },
      "confidence": float (0.0 to 1.0)
    }
  ]
}

Image dimensions for reference: {width}x{height}px
"""
```

### Chamada à API Claude

```python
import anthropic
import base64
import json
from PIL import Image

def detect_protected_regions(png_bytes: bytes) -> dict:
    img = Image.open(io.BytesIO(png_bytes))
    width, height = img.size
    
    client = anthropic.Anthropic()
    
    image_b64 = base64.standard_b64encode(png_bytes).decode("utf-8")
    
    prompt = PROTECTED_REGION_DETECTION_PROMPT.format(
        width=width, height=height
    )
    
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": image_b64,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    )
    
    raw = response.content[0].text.strip()
    return json.loads(raw)
```

### Geração de Máscara Binária

```python
from PIL import Image, ImageDraw
import numpy as np

def generate_protection_mask(
    image_size: tuple[int, int],
    protected_regions: list[dict],
    feather_px: int = 4
) -> np.ndarray:
    """
    Gera máscara binária onde:
    - 0 (preto) = região protegida, NÃO alterar
    - 255 (branco) = região livre para alteração de cor
    """
    mask = Image.new("L", image_size, 255)  # começa tudo branco (livre)
    draw = ImageDraw.Draw(mask)
    
    for region in protected_regions:
        bbox = region["bbox"]
        # Expandir bbox levemente para garantir cobertura
        x1 = max(0, bbox["x"] - feather_px)
        y1 = max(0, bbox["y"] - feather_px)
        x2 = min(image_size[0], bbox["x"] + bbox["width"] + feather_px)
        y2 = min(image_size[1], bbox["y"] + bbox["height"] + feather_px)
        draw.rectangle([x1, y1, x2, y2], fill=0)
    
    return np.array(mask)
```

---

## Etapa 3a — Variação de Cor

### Parâmetros Gemini Imagen (inpaint com máscara)

```python
import google.generativeai as genai

COLOR_VARIATION_PROMPT_TEMPLATE = """
Recolor this clothing item to {color_name} ({color_hex}).

Rules:
- Apply the new color ONLY to the white/unmasked areas
- Preserve ALL fabric texture, weave pattern, and natural folds
- Maintain realistic fabric shading and highlights for {color_name}
- Keep shadows proportional to the original
- The result must look like a real photograph, not a digital illustration
- Do NOT change any protected/masked regions
"""

def generate_color_variation(
    png_bytes: bytes,
    mask: np.ndarray,
    target_color_hex: str,
    target_color_name: str,
) -> bytes:
    model = genai.ImageGenerationModel("imagen-3.0-capability-001")
    
    # Converter máscara para bytes
    mask_img = Image.fromarray(mask)
    mask_bytes = io.BytesIO()
    mask_img.save(mask_bytes, format="PNG")
    
    prompt = COLOR_VARIATION_PROMPT_TEMPLATE.format(
        color_name=target_color_name,
        color_hex=target_color_hex,
    )
    
    response = model.edit_image(
        prompt=prompt,
        base_image=genai.types.Image(image_bytes=png_bytes),
        mask=genai.types.Image(image_bytes=mask_bytes.getvalue()),
        edit_mode="inpaint-insertion",
        number_of_images=1,
        guidance_scale=8.0,   # equilíbrio entre fidelidade e criatividade
    )
    
    return response.images[0]._image_bytes
```

### Critérios de Qualidade — Variação de Cor

| Critério | Aprovado | Rejeitar automaticamente |
|---|---|---|
| Textura preservada | Padrão do tecido visível | Cor sólida sem textura |
| Regiões protegidas | Inalteradas | Qualquer alteração visível |
| Bordas da peça | Nítidas, sem halo de cor | Halo colorido nas bordas |
| Naturalidade | Parece foto real | Parece pintura/ilustração |

**Se qualidade insuficiente:** retry com `guidance_scale` reduzido (6.0).  
**Máximo de retries:** 2.

---

## Etapa 3b — Fundo Alternativo

### Tipos de fundo

**Cor sólida:**
```python
def apply_solid_background(png_bytes: bytes, hex_color: str) -> bytes:
    img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    bg = Image.new("RGBA", img.size, hex_to_rgb(hex_color) + (255,))
    bg.paste(img, mask=img.split()[3])
    result = bg.convert("RGB")
    buf = io.BytesIO()
    result.save(buf, format="JPEG", quality=92)
    return buf.getvalue()
```

**Temático lifestyle (Gemini Imagen outpainting):**
```python
LIFESTYLE_BACKGROUND_PROMPTS = {
    "boutique": "elegant fashion boutique interior, soft natural lighting, white walls, wooden floor, minimalist decor, professional product photography",
    "urbano": "modern urban street, daytime, soft bokeh background, fashion editorial style",
    "estudio_clean": "clean professional studio, pure white seamless background, soft diffused lighting, high-key product shot",
    "praia_verao": "bright beach setting, turquoise water, golden sand, summer lifestyle photography",
    "cafe_lifestyle": "cozy coffee shop interior, warm tones, lifestyle fashion editorial",
}

def apply_lifestyle_background(
    png_bytes: bytes,
    background_style: str,
) -> bytes:
    prompt = f"""
    Place this clothing item in a {LIFESTYLE_BACKGROUND_PROMPTS[background_style]}.
    The garment must remain exactly as-is — same shape, same color, same details.
    Only add the background behind and around it.
    Result must look like a professional e-commerce lifestyle photo.
    """
    # Usar Gemini Imagen outpainting
    ...
```

---

## Etapa 4 — Export Padronizado

```python
from PIL import Image
import io

OUTPUT_RESOLUTION = (1200, 1200)
OUTPUT_QUALITY_JPG = 92

def export_for_platform(
    source_jpg: bytes,
    platform: str = "default"
) -> dict[str, bytes]:
    """
    Retorna dict com variantes por plataforma.
    """
    img = Image.open(io.BytesIO(source_jpg))
    
    # Redimensionar mantendo proporção, com padding branco para 1200×1200
    img.thumbnail(OUTPUT_RESOLUTION, Image.LANCZOS)
    canvas = Image.new("RGB", OUTPUT_RESOLUTION, (255, 255, 255))
    offset = (
        (OUTPUT_RESOLUTION[0] - img.width) // 2,
        (OUTPUT_RESOLUTION[1] - img.height) // 2,
    )
    canvas.paste(img, offset)
    
    buf = io.BytesIO()
    canvas.save(buf, format="JPEG", quality=OUTPUT_QUALITY_JPG)
    
    return {
        "jpg_1200": buf.getvalue(),
        "platform": platform,
        "resolution": "1200x1200",
    }
```

---

## Tratamento de Erros no Pipeline

| Situação | Ação |
|---|---|
| rembg confidence < 0.85 | Retry com Gemini Vision |
| Claude Vision retorna JSON inválido | Retry até 2x, depois `has_protected_regions: false` + flag manual |
| Gemini Imagen falha | Retry 1x com guidance_scale menor, depois `status: failed` |
| Imagem < 500×500px | Rejeitar no upload, retornar 422 |
| Imagem > 20MB | Rejeitar no upload, retornar 422 |
| Timeout de API (> 30s) | `status: failed`, notificar operador |

---

## Custo Estimado por Operação

| Operação | API | Custo aprox. |
|---|---|---|
| Remoção de fundo | rembg local | $0.00 |
| Remoção de fundo (fallback) | Gemini Vision | ~$0.01 |
| Detecção de regiões protegidas | Claude Vision | ~$0.01–0.02 |
| Variação de cor | Gemini Imagen | ~$0.02–0.04 |
| Fundo lifestyle | Gemini Imagen | ~$0.02–0.04 |
| Vídeo UGC (60s) | KlingAI | ~$0.10–0.30 |

Todos os custos são registrados em `generation_jobs.cost_cents`.
