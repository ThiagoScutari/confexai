---
name: confexai-seo-prompts
description: >
  Prompts e padrões para geração de descrições SEO do ConfexAI. Use esta SKILL
  sempre que for implementar, ajustar ou revisar a geração de descrições de
  produtos via Claude. Define os prompts exatos por plataforma (Mercado Livre,
  Shopee, Shopify), os campos obrigatórios, os limites de caracteres, as
  melhores práticas de SEO de cada plataforma, e o schema de retorno estruturado.
  Consulte antes de qualquer implementação ou ajuste no módulo de SEO.
---

# ConfexAI — Prompts e Padrões de SEO

## Visão Geral

O módulo de SEO usa **Claude claude-sonnet-4-20250514 com visão** para analisar a imagem
da peça e gerar títulos + descrições otimizados por plataforma, sem necessidade
de input manual do operador além do upload da imagem.

---

## Campos Gerados por Plataforma

| Campo | Mercado Livre | Shopee | Shopify |
|---|---|---|---|
| Título | máx. 60 chars | máx. 120 chars | máx. 70 chars |
| Descrição | máx. 4000 chars | máx. 3000 chars | sem limite prático |
| Tags/palavras-chave | até 5 tags | até 15 tags | meta keywords |
| Variações de cor | listadas no título | atributos separados | variantes |
| Cuidados de lavagem | obrigatório | obrigatório | recomendado |

---

## Prompt Base — Análise da Peça

```python
GARMENT_ANALYSIS_PROMPT = """
You are an expert in Brazilian fashion e-commerce and textile products.
Analyze this clothing item image carefully and extract the following information.
Return ONLY valid JSON, no markdown, no explanation.

{
  "garment_type": "string (ex: blusa, calça, vestido, saia, bermuda, conjunto)",
  "gender_target": "feminino" | "masculino" | "unissex" | "infantil",
  "modeling": "string (ex: slim fit, regular, oversized, cropped, longo, midi, mini)",
  "fabric_apparent": "string (ex: algodão, viscose, linho, malha, jeans, sintético)",
  "main_color": "string (nome da cor em português)",
  "has_print": boolean,
  "print_type": "string or null (ex: floral, listrado, xadrez, geométrico, liso)",
  "has_embroidery": boolean,
  "embroidery_description": "string or null",
  "notable_details": ["string"] (botões especiais, babados, renda, bolsos, etc.),
  "style": "string (ex: casual, social, esportivo, festa, praia, trabalho)",
  "season": "string (ex: verão, inverno, meia-estação, atemporal)",
  "wash_care_likely": "string (ex: lavar à mão, lavar à máquina fria, não torcer)"
}
"""
```

---

## Prompt de Geração — Mercado Livre

```python
ML_DESCRIPTION_PROMPT = """
You are a Brazilian Mercado Livre SEO specialist for fashion products.
Based on the garment analysis below and the product image, generate optimized 
listing content.

GARMENT DATA:
{garment_analysis_json}

COLORS AVAILABLE: {colors_list}

MERCADO LIVRE SEO RULES:
1. Title: máx 60 chars. Include: product type + key feature + gender + size range
   Format: [Tipo] [Feature Principal] [Gênero] – Tam [P ao GG ou numeração]
   Example: "Blusa Feminina Floral Viscose – Tam P ao GG"
2. Description must have: fabric, modeling, style, occasions, size guide hint, wash care
3. Use natural Brazilian Portuguese — avoid robotic language
4. Include size variants naturally in description, not as a list
5. Keywords must match what buyers actually search on ML Brazil

Return ONLY valid JSON:
{
  "title": "string (máx 60 chars)",
  "description": "string (400–800 chars, natural paragraphs, no markdown)",
  "keywords": ["string"] (5 keywords, most searched first),
  "title_char_count": integer,
  "seo_score_rationale": "string (brief explanation of choices)"
}
"""
```

---

## Prompt de Geração — Shopee

```python
SHOPEE_DESCRIPTION_PROMPT = """
You are a Brazilian Shopee SEO specialist for fashion products.
Based on the garment analysis below and the product image, generate optimized 
listing content.

GARMENT DATA:
{garment_analysis_json}

COLORS AVAILABLE: {colors_list}

SHOPEE SEO RULES:
1. Title: máx 120 chars. More descriptive than ML — include material and style
   Format: [Tipo] [Material] [Feature] [Gênero] [Estilo] + keywords naturais
   Example: "Blusa Feminina Viscose Manga Longa Floral Casual Elegante Moda+"
2. Description: use emojis moderadamente para destacar seções ✨👗
3. Structure: Features → Medidas/Tabela de tamanhos → Material → Cuidados
4. Tags: 15 tags relevantes — mix de genérico (blusa feminina) e específico (blusa floral viscose)
5. Brazilians on Shopee respond well to benefit-focused language

Return ONLY valid JSON:
{
  "title": "string (máx 120 chars)",
  "description": "string (600–1200 chars, with emojis for sections)",
  "tags": ["string"] (exactly 15 tags),
  "title_char_count": integer
}
"""
```

---

## Prompt de Geração — Shopify (Loja Própria)

```python
SHOPIFY_DESCRIPTION_PROMPT = """
You are a Brazilian fashion e-commerce copywriter for a brand's own Shopify store.
Based on the garment analysis below and the product image, generate premium 
product content that reflects brand quality.

GARMENT DATA:
{garment_analysis_json}

COLORS AVAILABLE: {colors_list}

SHOPIFY CONTENT RULES:
1. Title: máx 70 chars. Clean, brand-appropriate. No keyword stuffing.
   Format: [Tipo] [Nome/Feature] – [Material ou Estilo]
   Example: "Blusa Floral Manga Longa – Viscose Premium"
2. Description: editorial tone, evoke lifestyle and feeling
3. Structure: Opening hook (1 sentence) → Features bullet list → Care instructions
4. Meta description: 150-160 chars for Google SEO
5. Include structured data hints (fabric, care, occasion)
6. No emojis — professional tone

Return ONLY valid JSON:
{
  "title": "string (máx 70 chars)",
  "description_html": "string (HTML with <p> and <ul> tags, 200–500 words)",
  "meta_description": "string (150–160 chars)",
  "meta_keywords": ["string"] (8–10 keywords)
}
"""
```

---

## Implementação — Service de SEO

```python
import anthropic
import json
import base64

class SEOGeneratorService:
    
    def __init__(self):
        self.client = anthropic.Anthropic()
        self.model = "claude-sonnet-4-20250514"
    
    def analyze_garment(self, image_bytes: bytes) -> dict:
        """Passo 1: Extrair dados estruturados da peça."""
        image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
        
        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": image_b64,
                        },
                    },
                    {"type": "text", "text": GARMENT_ANALYSIS_PROMPT},
                ],
            }],
        )
        
        return json.loads(response.content[0].text)
    
    def generate_for_platform(
        self,
        garment_analysis: dict,
        colors: list[str],
        platform: str,
    ) -> dict:
        """Passo 2: Gerar descrição para plataforma específica."""
        
        prompt_map = {
            "mercadolivre": ML_DESCRIPTION_PROMPT,
            "shopee": SHOPEE_DESCRIPTION_PROMPT,
            "shopify": SHOPIFY_DESCRIPTION_PROMPT,
        }
        
        prompt = prompt_map[platform].format(
            garment_analysis_json=json.dumps(garment_analysis, ensure_ascii=False),
            colors_list=", ".join(colors),
        )
        
        response = self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        
        raw = response.content[0].text.strip()
        return json.loads(raw)
```

---

## Validações Pós-Geração

```python
def validate_seo_output(result: dict, platform: str) -> list[str]:
    """
    Retorna lista de warnings. Lista vazia = aprovado.
    """
    warnings = []
    
    limits = {
        "mercadolivre": {"title": 60},
        "shopee": {"title": 120},
        "shopify": {"title": 70},
    }
    
    title_limit = limits[platform]["title"]
    if len(result.get("title", "")) > title_limit:
        warnings.append(f"Título excede {title_limit} chars ({len(result['title'])} chars)")
    
    if platform == "shopee" and len(result.get("tags", [])) != 15:
        warnings.append(f"Shopee exige exatamente 15 tags ({len(result.get('tags', []))} geradas)")
    
    if platform == "shopify" and len(result.get("meta_description", "")) > 160:
        warnings.append("Meta description excede 160 chars")
    
    return warnings
```

---

## Exemplos de Output Esperado

### Mercado Livre — Blusa Floral Viscose
```json
{
  "title": "Blusa Feminina Floral Viscose Manga Longa – P ao GG",
  "description": "Blusa feminina em viscose leve com estampa floral delicada. Modelagem regular com manga longa e decote redondo. Ideal para o dia a dia com conforto e estilo. Disponível nas cores azul, coral e verde. Lavar à máquina em ciclo delicado, água fria. Não usar alvejante.",
  "keywords": ["blusa feminina", "blusa floral", "manga longa", "viscose", "blusa casual"],
  "title_char_count": 52
}
```

### Shopee — mesma blusa
```json
{
  "title": "Blusa Feminina Viscose Manga Longa Floral Casual Moda Feminina Verão Delicada",
  "description": "✨ BLUSA FLORAL FEMININA\n\n👗 Tecido viscose leve e macio\n🌸 Estampa floral delicada\n📏 Modelagem regular – cai bem em todos os biotipos\n\n🎨 Cores disponíveis: Azul | Coral | Verde\n\n🧺 CUIDADOS: Lavar na máquina ciclo delicado, água fria. Não torcer.",
  "tags": ["blusa feminina", "blusa floral", "manga longa", "viscose", "moda feminina", "blusa casual", "roupas femininas", "blusa elegante", "blusa estampada", "moda 2026", "blusa verão", "roupa feminina", "blusa básica", "roupas da moda", "blusa confortável"]
}
```

---

## Regras Implementadas (Sprint 12-13)

### Validação de Plataformas (ADR-012)
```python
# SEMPRE usar Literal — nunca list[str]
from typing import Literal
PlatformType = Literal["mercadolivre", "shopee", "shopify"]
platforms: list[PlatformType] = ["mercadolivre", "shopee", "shopify"]
```

### Rate Limiting (Sprint 13)
- 30 segundos por produto por usuário
- Retorna HTTP 429 com mensagem de espera
- Implementado via dict em memória (`_seo_rate_limit`)

### Campos do Banco (Sprint 13)
- `updated_at` atualizado a cada regeneração
- Índice composto `(product_id, platform)` para performance
- Segunda geração substitui (não duplica)

### Segurança (Sprint 12)
- Nunca usar `dangerouslySetInnerHTML` para renderizar descrições
- Usar `whitespace-pre-wrap` para texto simples
- `description_html` do Shopify renderizado como texto plano no MVP
