---
name: confexai-image-pipeline
description: >
  Padrões técnicos do pipeline de imagens do ConfexAI. Use esta SKILL sempre
  que for implementar ou revisar código relacionado a: remoção de fundo,
  detecção de regiões protegidas, variação de cor, ou qualquer operação de
  processamento de imagem. Define os fluxos exatos, ordem de operações,
  nomenclatura de arquivos e critérios de qualidade. CRÍTICO: contém as lições
  aprendidas do PDCA Sprint 16 sobre colisão de arquivos.
---

# ConfexAI — Pipeline de Imagens

## Fluxo Completo

```
Upload (original_{view}.{ext})
      ↓
Remoção de fundo (rembg — skip se já transparente)
      ↓
Detecção de regiões protegidas (Claude Vision)
      ↓
Variação de cor por view × cor (Gemini primário, Pillow fallback)
      ↓
Resultado: color_{HEX}_{VIEW}_{JOB_SHORT_ID}.{ext}
```

## REGRAS CRÍTICAS — Nomenclatura de Arquivos

### Upload
```python
# CORRETO — view no nome evita sobrescrita entre views
view_suffix = f"_{view}" if view else ""
file_path = product_dir / f"original{view_suffix}{Path(file.filename).suffix}"
# Resulta em: original_frente.png, original_costas.png, etc.

# PROIBIDO — sobrescreve outras views
file_path = product_dir / "original.png"
```

### Variação de Cor — LIÇÃO DO PDCA (Sprint 16)
```python
# CORRETO — job_short_id garante unicidade absoluta
# db.flush() ANTES de construir o path para ter job.id disponível
job = GenerationJob(type=..., status="pending", product_image_id=image.id)
db.add(job)
db.flush()  # ← OBRIGATÓRIO

job_short_id = str(job.id)[:8]
safe_hex = color_hex.replace("#", "").upper()
view_suffix = f"_{image.view}" if image.view else ""
output_path = Path(image_path).parent / f"color_{safe_hex}{view_suffix}_{job_short_id}.png"
# Resulta em: color_696980_frente_ae894d68.png

# PROIBIDO — colisão garantida entre execuções
output_path = Path(image_path).parent / f"color_{safe_hex}{view_suffix}.png"
```

**Por que é crítico:** sem `job_short_id`, re-executar o pipeline para a mesma
cor + view sobrescreve o arquivo anterior. Jobs mais antigos no banco apontam
para o arquivo mais recente — resultado: job de `frente` mostra imagem de
`lat_direita`. Validado com teste de ferro 4 views × 3 cores = 12 jobs.

## SDK Google Gemini (ADR-006)
```python
# CORRETO — google-genai SDK
from google import genai
from google.genai import types

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
response = client.models.generate_content(
    model="gemini-2.5-flash-image",
    contents=[
        types.Part.from_text(text=prompt),
        types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
    ],
    config=types.GenerateContentConfig(
        response_modalities=["IMAGE", "TEXT"],  # ← SEMPRE assim
    ),
)

# PROIBIDO — causa HTTP 400
generation_config={"response_mime_type": "image/png"}
```

## Result JSON — Campos Obrigatórios
```python
# O result de cada job DEVE conter:
result = {
    "jpg_url": "/static/uploads/{product_id}/color_{HEX}_{VIEW}_{SHORT_ID}.jpg",
    "png_url": "/static/uploads/{product_id}/color_{HEX}_{VIEW}_{SHORT_ID}.png",
    "color_hex": "#696980",   # ← SEMPRE incluir — frontend depende disso
    "method": "gemini",        # ou "pillow_fallback"
    "cost_cents": 3,           # 3 para Gemini, 0 para Pillow
}
```

## Pillow Fallback
```python
# Automático — registrar motivo
try:
    result = _apply_via_gemini(...)
    result["fallback_reason"] = None
except Exception as e:
    logger.warning(f"Gemini falhou: {e} — ativando Pillow")
    result = _apply_via_pillow(...)
    result["fallback_reason"] = f"Gemini erro: {str(e)[:200]}"

# cost_cents por método:
# Gemini: 3¢ | Pillow: 0¢ (local, gratuito)
```

## Métricas de Qualidade

Após cada geração Gemini, `_compute_quality_metrics` calcula:
- **edge_correlation** — correlação de Pearson entre bordas da original e resultado
  (< 0.05 = imagem completamente diferente)
- **color_distance** — distância euclidiana RGB entre cor média e target hex
  (> 150 = cor completamente errada)

Se qualquer limiar for violado, `quality_warning: true` no result JSON e badge
"Qualidade baixa" no frontend.

## Teste de Ferro

Após qualquer mudança no pipeline, executar obrigatoriamente:
- 4 views × 3 cores = 12 jobs
- Validar: 24 arquivos únicos (12 PNG + 12 JPG)
- Validar: todos via Gemini, color_hex correto, job_short_id no filename
- Aprovação do arquiteto obrigatória
