import anthropic
import base64
import json
import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)

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
  "print_type": "string or null",
  "has_embroidery": boolean,
  "embroidery_description": "string or null",
  "notable_details": ["string"],
  "style": "string (ex: casual, social, esportivo, festa, praia, trabalho)",
  "season": "string (ex: verão, inverno, meia-estação, atemporal)",
  "wash_care_likely": "string (ex: lavar à mão, lavar à máquina fria, não torcer)"
}
"""

ML_DESCRIPTION_PROMPT = """
You are a Brazilian Mercado Livre SEO specialist for fashion products.
Based on the garment analysis below and the product image, generate optimized listing content.

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
{{
  "title": "string (máx 60 chars)",
  "description": "string (400–800 chars, natural paragraphs, no markdown)",
  "keywords": ["string"],
  "title_char_count": integer,
  "seo_score_rationale": "string"
}}
"""

SHOPEE_DESCRIPTION_PROMPT = """
You are a Brazilian Shopee SEO specialist for fashion products.
Based on the garment analysis below and the product image, generate optimized listing content.

GARMENT DATA:
{garment_analysis_json}

COLORS AVAILABLE: {colors_list}

SHOPEE SEO RULES:
1. Title: máx 120 chars. More descriptive — include material and style
   Format: [Tipo] [Material] [Feature] [Gênero] [Estilo] + keywords naturais
2. Description: use emojis moderadamente para destacar seções ✨👗
3. Structure: Features → Material → Cuidados
4. Tags: exactly 15 tags — mix de genérico e específico
5. Benefit-focused language

Return ONLY valid JSON:
{{
  "title": "string (máx 120 chars)",
  "description": "string (600–1200 chars, with emojis)",
  "tags": ["string (exactly 15 items)"],
  "title_char_count": integer
}}
"""

SHOPIFY_DESCRIPTION_PROMPT = """
You are a Brazilian fashion e-commerce copywriter for a brand's own Shopify store.
Based on the garment analysis below and the product image, generate premium product content.

GARMENT DATA:
{garment_analysis_json}

COLORS AVAILABLE: {colors_list}

SHOPIFY CONTENT RULES:
1. Title: máx 70 chars. Clean, brand-appropriate. No keyword stuffing.
   Format: [Tipo] [Nome/Feature] – [Material ou Estilo]
2. Description: editorial tone, evoke lifestyle and feeling
3. Structure: Opening hook → Features list → Care instructions
4. Meta description: 150-160 chars for Google SEO
5. No emojis — professional tone

Return ONLY valid JSON:
{{
  "title": "string (máx 70 chars)",
  "description_html": "string (HTML with <p> and <ul> tags)",
  "meta_description": "string (150–160 chars)",
  "meta_keywords": ["string (8-10 items)"]
}}
"""

PLATFORM_PROMPTS = {
    "mercadolivre": ML_DESCRIPTION_PROMPT,
    "shopee": SHOPEE_DESCRIPTION_PROMPT,
    "shopify": SHOPIFY_DESCRIPTION_PROMPT,
}

TITLE_LIMITS = {
    "mercadolivre": 60,
    "shopee": 120,
    "shopify": 70,
}


class SEOGeneratorService:

    def __init__(self):
        self.client = anthropic.Anthropic()
        self.model = "claude-sonnet-4-20250514"

    def analyze_garment(self, image_bytes: bytes, media_type: str = "image/png") -> tuple[dict, int]:
        """
        Analisa a peça via Claude Vision.
        Retorna (analysis_dict, tokens_used).
        """
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
                            "media_type": media_type,
                            "data": image_b64,
                        },
                    },
                    {"type": "text", "text": GARMENT_ANALYSIS_PROMPT},
                ],
            }],
        )

        tokens = response.usage.input_tokens + response.usage.output_tokens
        raw = response.content[0].text.strip()

        try:
            return json.loads(raw), tokens
        except json.JSONDecodeError as e:
            logger.error(f"Claude retornou JSON inválido na análise: {e} | raw: {raw[:200]}")
            raise ValueError(f"Falha ao analisar peça: resposta inválida do modelo")

    def generate_for_platform(
        self,
        garment_analysis: dict,
        colors: list[str],
        platform: str,
    ) -> tuple[dict, int, list[str]]:
        """
        Gera descrição SEO para uma plataforma específica.
        Retorna (result_dict, tokens_used, warnings).
        """
        if platform not in PLATFORM_PROMPTS:
            raise ValueError(f"Plataforma inválida: {platform}. Use: {list(PLATFORM_PROMPTS.keys())}")

        prompt = PLATFORM_PROMPTS[platform].format(
            garment_analysis_json=json.dumps(garment_analysis, ensure_ascii=False),
            colors_list=", ".join(colors) if colors else "não informado",
        )

        response = self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )

        tokens = response.usage.input_tokens + response.usage.output_tokens
        raw = response.content[0].text.strip()

        try:
            result = json.loads(raw)
        except json.JSONDecodeError as e:
            logger.error(f"Claude retornou JSON inválido para {platform}: {e} | raw: {raw[:200]}")
            raise ValueError(f"Falha ao gerar SEO para {platform}: resposta inválida")

        warnings = self._validate(result, platform)
        return result, tokens, warnings

    def _validate(self, result: dict, platform: str) -> list[str]:
        """Valida limites de caracteres e campos obrigatórios."""
        warnings = []
        limit = TITLE_LIMITS.get(platform, 999)
        title = result.get("title", "")

        if len(title) > limit:
            warnings.append(f"Título excede {limit} chars ({len(title)} chars)")

        if platform == "shopee":
            tags = result.get("tags", [])
            if len(tags) != 15:
                warnings.append(f"Shopee exige 15 tags ({len(tags)} geradas)")

        if platform == "shopify":
            meta = result.get("meta_description", "")
            if len(meta) > 160:
                warnings.append(f"Meta description excede 160 chars ({len(meta)} chars)")

        return warnings
