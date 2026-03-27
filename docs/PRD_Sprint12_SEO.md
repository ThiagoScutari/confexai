# PRD — Sprint 12: Descrições SEO por Plataforma

**Status:** Aprovação Pendente
**Origem:** Feature — módulo de SEO para Mercado Livre, Shopee e Shopify
**Data:** 2026-03-26
**Objetivo:** Claude analisa a imagem da peça e gera título + descrição otimizados para cada plataforma, com validação de limites de caracteres e armazenamento no banco.

---

## Fluxo do Módulo SEO

```
[Imagem da peça (view=frente preferencialmente)]
        ↓
[Claude Vision analisa a peça]
        → garment_type, fabric, modeling, style, details...
        ↓
[Para cada plataforma selecionada]
        → Gerar título + descrição + tags
        → Validar limites de caracteres
        → Salvar em seo_descriptions
        ↓
[Exibir no frontend com opção de edição e cópia]
```

---

## Sumário Executivo

| ID | Tipo | Descrição | Esforço |
|---|---|---|---|
| S12-01 | feat | Service `SEOGeneratorService` com análise + geração por plataforma | Médio |
| S12-02 | feat | Endpoint `POST /api/v1/products/{id}/seo` | Médio |
| S12-03 | feat | Endpoint `GET /api/v1/products/{id}/seo` | Pequeno |
| S12-04 | feat | Frontend: aba "SEO" na página do produto com geração e edição | Médio |
| S12-05 | test | Testes com mock do Claude para os 3 endpoints | Médio |

---

## S12-01 — Service SEOGeneratorService

### `backend/app/services/seo_generator.py`

```python
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
```

---

## S12-02 — Endpoint POST /products/{id}/seo

### Adicionar em `backend/app/api/products.py`

```python
import json
import time
from app.services.seo_generator import SEOGeneratorService
from app.models import SEODescription, ProductImage
from app.services.url_helper import path_to_url
from pydantic import BaseModel

class SEOGenerateRequest(BaseModel):
    platforms: list[str] = ["mercadolivre", "shopee", "shopify"]
    colors: list[str] = []  # HEX colors available for this product
    image_id: str | None = None  # usar imagem específica; se None, usa frente


@router.post("/{product_id}/seo", status_code=202)
def generate_seo(
    product_id: UUID,
    payload: SEOGenerateRequest,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """
    Gera descrições SEO para o produto via Claude Vision.
    Usa a imagem de frente preferencialmente.
    """
    # Verificar produto
    product = db.query(Product).filter(
        Product.id == product_id, Product.is_active == True
    ).first()
    if not product:
        raise HTTPException(404, detail="Produto não encontrado.")

    # Buscar imagem para análise
    if payload.image_id:
        image = db.query(ProductImage).filter(
            ProductImage.id == payload.image_id,
            ProductImage.product_id == product_id,
        ).first()
    else:
        # Preferir frente; fallback para qualquer imagem original
        image = db.query(ProductImage).filter(
            ProductImage.product_id == product_id,
            ProductImage.type == "original",
            ProductImage.view == "frente",
        ).first() or db.query(ProductImage).filter(
            ProductImage.product_id == product_id,
            ProductImage.type == "original",
        ).first()

    if not image:
        raise HTTPException(422, detail="Produto sem imagens. Faça upload primeiro.")

    image_path = image.processed_url or image.original_url
    if not image_path:
        raise HTTPException(422, detail="Imagem sem URL processada.")

    try:
        with open(image_path, "rb") as f:
            image_bytes = f.read()
    except FileNotFoundError:
        raise HTTPException(422, detail="Arquivo de imagem não encontrado no disco.")

    svc = SEOGeneratorService()
    results = []
    total_tokens = 0
    total_cost_cents = 0

    try:
        # Passo 1: Analisar a peça
        start = int(time.time() * 1000)
        garment_analysis, analysis_tokens = svc.analyze_garment(image_bytes)
        analysis_duration = int(time.time() * 1000) - start
        total_tokens += analysis_tokens

        # Passo 2: Gerar para cada plataforma
        for platform in payload.platforms:
            try:
                plat_start = int(time.time() * 1000)
                result, tokens, warnings = svc.generate_for_platform(
                    garment_analysis=garment_analysis,
                    colors=payload.colors,
                    platform=platform,
                )
                duration = int(time.time() * 1000) - plat_start
                total_tokens += tokens

                # Custo estimado: ~$0.03 por 1K tokens Claude Sonnet
                cost = max(1, round((tokens / 1000) * 3))
                total_cost_cents += cost

                # Preparar campos por plataforma
                if platform == "shopify":
                    title = result.get("title", "")
                    description = result.get("description_html", "")
                    tags = result.get("meta_keywords", [])
                else:
                    title = result.get("title", "")
                    description = result.get("description", "")
                    tags = result.get("keywords", result.get("tags", []))

                # Salvar no banco (substituir se já existe para esta plataforma)
                existing = db.query(SEODescription).filter(
                    SEODescription.product_id == product_id,
                    SEODescription.platform == platform,
                ).first()

                if existing:
                    existing.title = title
                    existing.description = description
                    existing.tags = json.dumps(tags, ensure_ascii=False)
                    existing.is_approved = False
                else:
                    seo = SEODescription(
                        product_id=product_id,
                        platform=platform,
                        title=title,
                        description=description,
                        tags=json.dumps(tags, ensure_ascii=False),
                    )
                    db.add(seo)

                db.commit()

                results.append({
                    "platform": platform,
                    "title": title,
                    "title_char_count": len(title),
                    "description_preview": description[:150] + "..." if len(description) > 150 else description,
                    "tags_count": len(tags),
                    "warnings": warnings,
                    "cost_cents": cost,
                    "duration_ms": duration,
                })

            except Exception as e:
                logger.error(f"Falha ao gerar SEO para {platform}: {e}", exc_info=True)
                results.append({
                    "platform": platform,
                    "error": str(e),
                    "cost_cents": 0,
                })

    except Exception as e:
        logger.error(f"Falha na análise da peça: {e}", exc_info=True)
        raise HTTPException(500, detail=f"Erro ao analisar peça: {str(e)}")

    return StandardResponse(data={
        "product_id": str(product_id),
        "garment_analysis": garment_analysis,
        "results": results,
        "total_tokens": total_tokens,
        "total_cost_cents": total_cost_cents,
    })
```

---

## S12-03 — Endpoint GET /products/{id}/seo

### Adicionar em `backend/app/api/products.py`

```python
@router.get("/{product_id}/seo")
def get_seo_descriptions(
    product_id: UUID,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Lista todas as descrições SEO geradas para o produto."""
    product = db.query(Product).filter(
        Product.id == product_id, Product.is_active == True
    ).first()
    if not product:
        raise HTTPException(404, detail="Produto não encontrado.")

    descriptions = db.query(SEODescription).filter(
        SEODescription.product_id == product_id
    ).all()

    return StandardResponse(data=[
        {
            "id": str(d.id),
            "platform": d.platform,
            "title": d.title,
            "title_char_count": len(d.title),
            "description": d.description,
            "tags": json.loads(d.tags) if d.tags else [],
            "is_approved": d.is_approved,
            "created_at": d.created_at.isoformat(),
        }
        for d in descriptions
    ])
```

---

## S12-04 — Frontend: Página SEO

### Adicionar em `frontend/src/services/api.js`

```javascript
export const generateSEO = (productId, platforms, colors, imageId = null) =>
  api.post(`/products/${productId}/seo`, {
    platforms,
    colors,
    image_id: imageId,
  });

export const getSEO = (productId) =>
  api.get(`/products/${productId}/seo`);
```

### Nova página `frontend/src/pages/SEO.jsx`

```jsx
import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Sparkles, Copy, Check, AlertTriangle, ArrowLeft, RefreshCw } from "lucide-react";
import { generateSEO, getSEO, getProduct } from "../services/api";
import { useToast } from "../components/Toast";

const PLATFORMS = [
  { key: "mercadolivre", label: "Mercado Livre", color: "text-yellow-400", limit: 60 },
  { key: "shopee", label: "Shopee", color: "text-orange-400", limit: 120 },
  { key: "shopify", label: "Shopify", color: "text-green-400", limit: 70 },
];

const DEFAULT_COLORS = ["#696980", "#978b7b", "#9e987d"];

export default function SEO() {
  const { productId } = useParams();
  const navigate = useNavigate();
  const { toast } = useToast();

  const [product, setProduct] = useState(null);
  const [descriptions, setDescriptions] = useState([]);
  const [generating, setGenerating] = useState(false);
  const [selectedPlatforms, setSelectedPlatforms] = useState(["mercadolivre", "shopee", "shopify"]);
  const [colors, setColors] = useState(DEFAULT_COLORS);
  const [analysis, setAnalysis] = useState(null);
  const [copied, setCopied] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      getProduct(productId),
      getSEO(productId),
    ]).then(([prodRes, seoRes]) => {
      setProduct(prodRes.data.data);
      setDescriptions(seoRes.data.data);
    }).catch(() => toast("Erro ao carregar produto", "error"))
      .finally(() => setLoading(false));
  }, [productId]);

  const handleGenerate = async () => {
    if (selectedPlatforms.length === 0) {
      toast("Selecione ao menos uma plataforma", "warning");
      return;
    }
    setGenerating(true);
    try {
      const res = await generateSEO(productId, selectedPlatforms, colors);
      const data = res.data.data;
      setAnalysis(data.garment_analysis);

      // Recarregar descrições do banco
      const seoRes = await getSEO(productId);
      setDescriptions(seoRes.data.data);

      const totalCost = data.total_cost_cents;
      toast(
        `${selectedPlatforms.length} descrições geradas — ${totalCost}¢ (R$${(totalCost * 0.006).toFixed(2)})`,
        "success"
      );

      // Avisar sobre warnings
      const withWarnings = data.results.filter(r => r.warnings?.length > 0);
      if (withWarnings.length > 0) {
        toast(`${withWarnings.length} plataforma(s) com avisos — verifique os títulos`, "warning");
      }
    } catch (err) {
      toast(err.response?.data?.detail || "Erro ao gerar SEO", "error");
    } finally {
      setGenerating(false);
    }
  };

  const copyToClipboard = async (text, key) => {
    await navigator.clipboard.writeText(text);
    setCopied(key);
    setTimeout(() => setCopied(null), 2000);
  };

  const togglePlatform = (key) => {
    setSelectedPlatforms(prev =>
      prev.includes(key) ? prev.filter(p => p !== key) : [...prev, key]
    );
  };

  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-center gap-4 mb-8">
        <button onClick={() => navigate("/produtos")} className="text-neutral-500 hover:text-neutral-300">
          <ArrowLeft size={18} />
        </button>
        <div className="flex-1">
          <p className="text-xs text-neutral-500 uppercase tracking-wider mb-0.5">Descrições SEO</p>
          <h1 className="font-display text-2xl text-neutral-100">
            {product?.name || "Carregando..."}
          </h1>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-6">
        {/* Coluna esquerda — configuração */}
        <div className="space-y-4">
          {/* Seleção de plataformas */}
          <div className="bg-surface-800 border border-surface-600 rounded-xl p-4">
            <p className="text-xs text-neutral-500 uppercase tracking-wider mb-3">Plataformas</p>
            <div className="space-y-2">
              {PLATFORMS.map(({ key, label, color }) => (
                <button
                  key={key}
                  onClick={() => togglePlatform(key)}
                  className={`w-full flex items-center justify-between px-3 py-2 rounded-lg border transition-all text-sm ${
                    selectedPlatforms.includes(key)
                      ? "border-amber-500/40 bg-amber-500/5 text-neutral-100"
                      : "border-surface-600 bg-surface-700 text-neutral-400"
                  }`}
                >
                  <span className={selectedPlatforms.includes(key) ? color : ""}>{label}</span>
                  {selectedPlatforms.includes(key) && <Check size={14} className="text-amber-400" />}
                </button>
              ))}
            </div>
          </div>

          {/* Análise da peça */}
          {analysis && (
            <div className="bg-surface-800 border border-surface-600 rounded-xl p-4">
              <p className="text-xs text-neutral-500 uppercase tracking-wider mb-3">Análise da peça</p>
              <div className="space-y-1.5 text-xs">
                {[
                  ["Tipo", analysis.garment_type],
                  ["Público", analysis.gender_target],
                  ["Modelagem", analysis.modeling],
                  ["Tecido", analysis.fabric_apparent],
                  ["Estilo", analysis.style],
                  ["Estação", analysis.season],
                  ["Lavagem", analysis.wash_care_likely],
                ].map(([label, value]) => value && (
                  <div key={label} className="flex justify-between">
                    <span className="text-neutral-500">{label}</span>
                    <span className="text-neutral-300 text-right max-w-32 truncate">{value}</span>
                  </div>
                ))}
                {analysis.notable_details?.length > 0 && (
                  <div>
                    <span className="text-neutral-500">Detalhes</span>
                    <p className="text-neutral-300 mt-0.5">{analysis.notable_details.join(", ")}</p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Botão gerar */}
          <button
            onClick={handleGenerate}
            disabled={generating || selectedPlatforms.length === 0}
            className="w-full flex items-center justify-center gap-2 py-3 bg-amber-500 hover:bg-amber-400 disabled:opacity-40 disabled:cursor-not-allowed text-surface-950 rounded-xl font-medium transition-colors"
          >
            {generating ? (
              <><RefreshCw size={16} className="animate-spin" /> Gerando...</>
            ) : (
              <><Sparkles size={16} /> Gerar SEO</>
            )}
          </button>
        </div>

        {/* Coluna direita — resultados */}
        <div className="col-span-2 space-y-4">
          {loading ? (
            <div className="space-y-3">
              {[1, 2, 3].map(i => (
                <div key={i} className="bg-surface-800 border border-surface-700 rounded-xl h-40 animate-pulse" />
              ))}
            </div>
          ) : descriptions.length === 0 ? (
            <div className="text-center py-20 text-neutral-600">
              <Sparkles size={40} className="mx-auto mb-3 opacity-30" />
              <p className="text-sm">Nenhuma descrição gerada ainda</p>
              <p className="text-xs mt-1">Selecione as plataformas e clique em Gerar SEO</p>
            </div>
          ) : (
            PLATFORMS.filter(p => descriptions.find(d => d.platform === p.key)).map(({ key, label, color, limit }) => {
              const desc = descriptions.find(d => d.platform === key);
              if (!desc) return null;

              const titleOver = desc.title_char_count > limit;
              const tags = Array.isArray(desc.tags) ? desc.tags : [];

              return (
                <div key={key} className="bg-surface-800 border border-surface-600 rounded-xl p-5">
                  {/* Platform header */}
                  <div className="flex items-center justify-between mb-4">
                    <span className={`text-sm font-medium ${color}`}>{label}</span>
                    <span className="text-xs text-neutral-600">
                      {new Date(desc.created_at).toLocaleString("pt-BR")}
                    </span>
                  </div>

                  {/* Título */}
                  <div className="mb-3">
                    <div className="flex items-center justify-between mb-1">
                      <p className="text-xs text-neutral-500">Título</p>
                      <div className="flex items-center gap-2">
                        {titleOver && <AlertTriangle size={12} className="text-red-400" />}
                        <span className={`text-xs font-mono ${titleOver ? "text-red-400" : "text-neutral-500"}`}>
                          {desc.title_char_count}/{limit}
                        </span>
                        <button
                          onClick={() => copyToClipboard(desc.title, `${key}-title`)}
                          className="text-neutral-600 hover:text-amber-400 transition-colors"
                        >
                          {copied === `${key}-title` ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} />}
                        </button>
                      </div>
                    </div>
                    <p className="text-sm text-neutral-100 bg-surface-700 rounded px-3 py-2">
                      {desc.title}
                    </p>
                  </div>

                  {/* Descrição */}
                  <div className="mb-3">
                    <div className="flex items-center justify-between mb-1">
                      <p className="text-xs text-neutral-500">Descrição</p>
                      <button
                        onClick={() => copyToClipboard(desc.description, `${key}-desc`)}
                        className="text-neutral-600 hover:text-amber-400 transition-colors"
                      >
                        {copied === `${key}-desc` ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} />}
                      </button>
                    </div>
                    <div
                      className="text-sm text-neutral-300 bg-surface-700 rounded px-3 py-2 max-h-32 overflow-auto whitespace-pre-wrap"
                      dangerouslySetInnerHTML={{ __html: desc.description }}
                    />
                  </div>

                  {/* Tags */}
                  {tags.length > 0 && (
                    <div>
                      <div className="flex items-center justify-between mb-1">
                        <p className="text-xs text-neutral-500">Tags ({tags.length})</p>
                        <button
                          onClick={() => copyToClipboard(tags.join(", "), `${key}-tags`)}
                          className="text-neutral-600 hover:text-amber-400 transition-colors"
                        >
                          {copied === `${key}-tags` ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} />}
                        </button>
                      </div>
                      <div className="flex flex-wrap gap-1">
                        {tags.map((tag, i) => (
                          <span key={i} className="text-xs bg-surface-700 text-neutral-400 px-2 py-0.5 rounded">
                            {tag}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
```

### Adicionar à sidebar e rotas

**Layout.jsx:**
```jsx
import { Package, Images, Zap, ScrollText, Tag } from "lucide-react";

const navItems = [
  { to: "/produtos", icon: Package, label: "Produtos" },
  { to: "/resultados", icon: Images, label: "Resultados" },
  { to: "/historico", icon: ScrollText, label: "Histórico" },
  { to: "/pipeline", icon: Zap, label: "Novo Pipeline" },
];
```

> SEO é acessado via produto (não sidebar direta) — botão "SEO" em cada card de produto.

**App.jsx:**
```jsx
import SEO from "./pages/SEO";
// ...
<Route path="seo/:productId" element={<SEO />} />
```

**Produtos.jsx — adicionar botão SEO em cada card:**
```jsx
<button
  onClick={(e) => { e.stopPropagation(); navigate(`/seo/${p.id}`); }}
  className="px-3 py-1.5 text-xs bg-surface-700 hover:bg-surface-600 border border-surface-600 text-neutral-300 rounded-md transition-colors"
>
  SEO
</button>
```

---

## S12-05 — Testes

### `backend/tests/test_seo.py`

```python
import json
import pytest
from unittest.mock import patch, MagicMock


MOCK_ANALYSIS = {
    "garment_type": "blusa",
    "gender_target": "feminino",
    "modeling": "regular",
    "fabric_apparent": "viscose",
    "main_color": "azul",
    "has_print": False,
    "print_type": None,
    "has_embroidery": False,
    "embroidery_description": None,
    "notable_details": [],
    "style": "casual",
    "season": "atemporal",
    "wash_care_likely": "lavar à máquina fria",
}

MOCK_ML_RESULT = {
    "title": "Blusa Feminina Viscose Casual – Tam P ao GG",
    "description": "Blusa feminina em viscose leve e macia. Modelagem regular, ideal para o dia a dia.",
    "keywords": ["blusa feminina", "viscose", "casual"],
    "title_char_count": 43,
    "seo_score_rationale": "Inclui tipo, material e público-alvo.",
}

MOCK_SHOPEE_RESULT = {
    "title": "Blusa Feminina Viscose Casual Moda Feminina Confortável",
    "description": "✨ BLUSA FEMININA\n\n👗 Tecido viscose macio\n\n🧺 Lavar à máquina fria",
    "tags": [f"tag{i}" for i in range(15)],
    "title_char_count": 54,
}

MOCK_SHOPIFY_RESULT = {
    "title": "Blusa Casual – Viscose Premium",
    "description_html": "<p>Uma blusa elegante para o dia a dia.</p>",
    "meta_description": "Blusa feminina casual em viscose, modelagem regular. Conforto e estilo para o dia a dia.",
    "meta_keywords": ["blusa", "viscose", "feminina"],
}


def _mock_seo_service():
    mock = MagicMock()
    mock.analyze_garment.return_value = (MOCK_ANALYSIS, 500)
    mock.generate_for_platform.side_effect = lambda garment_analysis, colors, platform: {
        "mercadolivre": (MOCK_ML_RESULT, 300, []),
        "shopee": (MOCK_SHOPEE_RESULT, 400, []),
        "shopify": (MOCK_SHOPIFY_RESULT, 350, []),
    }[platform]
    return mock


def test_gerar_seo_sem_token_retorna_401(client, sample_product):
    response = client.post(f"/api/v1/products/{sample_product.id}/seo", json={})
    assert response.status_code == 401


def test_gerar_seo_produto_inexistente_retorna_404(client, auth_headers):
    with patch("app.api.products.SEOGeneratorService") as MockSvc:
        MockSvc.return_value = _mock_seo_service()
        response = client.post(
            "/api/v1/products/00000000-0000-0000-0000-000000000000/seo",
            json={"platforms": ["mercadolivre"]},
            headers=auth_headers,
        )
    assert response.status_code == 404


def test_gerar_seo_produto_sem_imagem_retorna_422(client, auth_headers, sample_product):
    with patch("app.api.products.SEOGeneratorService") as MockSvc:
        MockSvc.return_value = _mock_seo_service()
        response = client.post(
            f"/api/v1/products/{sample_product.id}/seo",
            json={"platforms": ["mercadolivre"]},
            headers=auth_headers,
        )
    assert response.status_code == 422


def test_gerar_seo_retorna_202_com_resultados(
    client, auth_headers, sample_product, sample_image_uploaded
):
    with patch("app.api.products.SEOGeneratorService") as MockSvc:
        MockSvc.return_value = _mock_seo_service()
        response = client.post(
            f"/api/v1/products/{sample_product.id}/seo",
            json={"platforms": ["mercadolivre", "shopee"], "colors": ["#696980"]},
            headers=auth_headers,
        )
    assert response.status_code == 202
    data = response.json()["data"]
    assert "garment_analysis" in data
    assert len(data["results"]) == 2
    assert data["results"][0]["platform"] in ["mercadolivre", "shopee"]


def test_listar_seo_sem_token_retorna_401(client, sample_product):
    response = client.get(f"/api/v1/products/{sample_product.id}/seo")
    assert response.status_code == 401


def test_listar_seo_retorna_200(client, auth_headers, sample_product):
    response = client.get(
        f"/api/v1/products/{sample_product.id}/seo",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert isinstance(response.json()["data"], list)


def test_gerar_seo_salva_no_banco(
    client, auth_headers, sample_product, sample_image_uploaded, db
):
    from app.models import SEODescription
    with patch("app.api.products.SEOGeneratorService") as MockSvc:
        MockSvc.return_value = _mock_seo_service()
        client.post(
            f"/api/v1/products/{sample_product.id}/seo",
            json={"platforms": ["mercadolivre"], "colors": []},
            headers=auth_headers,
        )
    saved = db.query(SEODescription).filter(
        SEODescription.product_id == sample_product.id,
        SEODescription.platform == "mercadolivre",
    ).first()
    assert saved is not None
    assert saved.title == MOCK_ML_RESULT["title"]


def test_gerar_seo_substitui_descricao_existente(
    client, auth_headers, sample_product, sample_image_uploaded, db
):
    """Gerar duas vezes deve substituir, não duplicar."""
    from app.models import SEODescription
    with patch("app.api.products.SEOGeneratorService") as MockSvc:
        MockSvc.return_value = _mock_seo_service()
        client.post(
            f"/api/v1/products/{sample_product.id}/seo",
            json={"platforms": ["shopee"], "colors": []},
            headers=auth_headers,
        )
        client.post(
            f"/api/v1/products/{sample_product.id}/seo",
            json={"platforms": ["shopee"], "colors": []},
            headers=auth_headers,
        )
    count = db.query(SEODescription).filter(
        SEODescription.product_id == sample_product.id,
        SEODescription.platform == "shopee",
    ).count()
    assert count == 1  # não deve duplicar
```

> **Nota:** `sample_image_uploaded` é uma fixture nova no `conftest.py` — cria um `ProductImage` com arquivo real em disco para o `sample_product`.

---

## Ordem de Execução

```
S12-01 (service seo_generator.py)
  ↓
S12-02 + S12-03 (endpoints em products.py)
  ↓
S12-05 (testes — com mock do Claude)
  ↓
Rodar testes (target: 63 passed, 0 failed)
  ↓
S12-04 (frontend: SEO.jsx + rota + botão em Produtos)
  ↓
Build frontend + verificação visual
  ↓
Commits
```

---

## Commits Atômicos

```
feat(api): add SEOGeneratorService with Claude Vision analysis and platform generation [S12-01]
feat(api): add POST /products/{id}/seo and GET /products/{id}/seo endpoints [S12-02-03]
test(sprint12): add 8 tests for SEO generation with Claude mock [S12-05]
feat(frontend): add SEO page with platform cards, copy buttons and garment analysis [S12-04]
feat(frontend): add SEO button per product in Produtos list [S12-04]
```

---

## Critérios de Aceite

- [ ] `POST /products/{id}/seo` gera título + descrição para ML, Shopee e Shopify
- [ ] Análise da peça retorna `garment_type`, `fabric`, `style` etc.
- [ ] Título do ML respeita 60 chars (aviso se exceder)
- [ ] Shopee tem exatamente 15 tags
- [ ] Shopify tem meta description 150-160 chars
- [ ] Segunda geração substitui a anterior (não duplica no banco)
- [ ] Frontend mostra card por plataforma com título, descrição e tags
- [ ] Botão de cópia funciona para título, descrição e tags separadamente
- [ ] Custo em centavos e R$ aparece no toast após geração
- [ ] `pytest tests/ -v` → **63 passed, 0 failed**
