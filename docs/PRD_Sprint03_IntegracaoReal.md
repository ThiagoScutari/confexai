# PRD — Sprint 03: Integração Real com APIs e Validação do Pipeline

**Status:** Aprovação Pendente  
**Origem:** Validação de integração — primeiro uso real de Anthropic e Gemini  
**Data:** 2026-03-26  
**Objetivo:** Executar o pipeline completo com as imagens de `examples/` usando APIs reais. Validar qualidade dos resultados e custo por operação antes de escalar.

---

## ⚠️ Natureza Diferente deste Sprint

Este não é um sprint de features — é um sprint de **integração e validação**.

O risco central é a chamada ao **Gemini Imagen** para variação de cor. O serviço `color_variation.py` foi escrito com `gemini-2.0-flash-exp` + `response_mime_type: image/png`, mas a API real pode ter comportamento diferente do esperado. Por isso este sprint tem **duas fases obrigatórias**:

- **Fase A — Prova de Conceito (1 imagem, 1 cor):** validar que a chamada Gemini funciona e gera resultado aceitável
- **Fase B — Pipeline Completo (4 views, 3 cores):** escalar após validação da Fase A

Custo estimado deste sprint: **R$ 1,00 ~ R$ 5,00** em APIs.

---

## Sumário Executivo

| ID | Tipo | Descrição | Risco |
|---|---|---|---|
| S03-01 | devops | Script de seed para criar produto e fazer upload das 4 views | Baixo |
| S03-02 | feat | Ajuste do serviço Gemini se API real divergir do esperado | Médio |
| S03-03 | feat | Fase A — POC: 1 imagem × 1 cor via API real | Alto |
| S03-04 | feat | Fase B — Pipeline completo: 4 views × 3 cores | Médio |
| S03-05 | feat | Export dos assets aprovados | Baixo |
| S03-06 | docs | Registro de custos reais e ajustes de estimativa | Baixo |

---

## S03-01 — Script de Seed

Criar script para popular o banco com o produto de teste e fazer upload das 4 imagens de `examples/roupa/` via API.

### `backend/scripts/seed_sprint03.py`

```python
"""
Seed Sprint 03 — Cria produto de teste e faz upload das 4 views.
Executar: docker compose exec api python backend/scripts/seed_sprint03.py
"""
import os
import sys
import requests
from pathlib import Path

BASE_URL = "http://localhost:8002/api/v1"  # ajustar porta se diferente
EXAMPLES_DIR = Path("/app/examples/roupa")

VIEWS = ["frente", "costas", "lat_direita", "lat_esquerda"]
VIEW_FILES = {
    "frente": "frente.png",
    "costas": "costas.png",
    "lat_direita": "lat_direita.png",
    "lat_esquerda": "lat_esquerda.png",
}


def get_token() -> str:
    r = requests.post(f"{BASE_URL}/auth/login", json={
        "email": os.getenv("ADMIN_EMAIL", "admin@confexai.local"),
        "password": os.getenv("ADMIN_PASSWORD", "admin123"),
    })
    r.raise_for_status()
    return r.json()["data"]["access_token"]


def create_product(token: str) -> str:
    r = requests.post(
        f"{BASE_URL}/products",
        json={
            "name": "Peça Teste Sprint 03 — Lisa",
            "category": "blusa",
            "fabric": "viscose",
            "notes": "Peça de teste para validação do pipeline de variação de cor",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    r.raise_for_status()
    product_id = r.json()["data"]["id"]
    print(f"✅ Produto criado: {product_id}")
    return product_id


def upload_images(token: str, product_id: str) -> dict[str, str]:
    image_ids = {}
    for view, filename in VIEW_FILES.items():
        filepath = EXAMPLES_DIR / filename
        if not filepath.exists():
            print(f"⚠️  Arquivo não encontrado: {filepath}")
            continue

        with open(filepath, "rb") as f:
            r = requests.post(
                f"{BASE_URL}/products/{product_id}/images/upload",
                files={"file": (filename, f, "image/png")},
                params={"view": view},
                headers={"Authorization": f"Bearer {token}"},
            )
        r.raise_for_status()
        image_id = r.json()["data"]["id"]
        image_ids[view] = image_id
        print(f"✅ Upload {view}: {image_id}")

    return image_ids


def main():
    print("=== Seed Sprint 03 ===")
    token = get_token()
    print(f"✅ Token obtido")

    product_id = create_product(token)
    image_ids = upload_images(token, product_id)

    print("\n=== IDs para usar nos próximos passos ===")
    print(f"PRODUCT_ID={product_id}")
    for view, img_id in image_ids.items():
        print(f"IMAGE_ID_{view.upper()}={img_id}")

    # Salvar IDs em arquivo para referência
    with open("/app/backend/scripts/sprint03_ids.txt", "w") as f:
        f.write(f"PRODUCT_ID={product_id}\n")
        for view, img_id in image_ids.items():
            f.write(f"IMAGE_ID_{view.upper()}={img_id}\n")
    print("\n✅ IDs salvos em backend/scripts/sprint03_ids.txt")


if __name__ == "__main__":
    main()
```

---

## S03-02 — Validação e Ajuste do Serviço Gemini

### Problema potencial

O serviço `color_variation.py` foi escrito com:

```python
model = genai.GenerativeModel("gemini-2.0-flash-exp")
response = model.generate_content(
    [prompt, {"mime_type": "image/png", "data": image_bytes}],
    generation_config={"response_mime_type": "image/png"},
)
result_bytes = response.candidates[0].content.parts[0].inline_data.data
```

Esta abordagem pede ao Gemini Flash que **gere** uma imagem PNG como resposta. É a forma mais simples mas pode ter limitações:
- O modelo pode não suportar `response_mime_type: image/png` em todas as versões
- A qualidade do inpainting pode ser inferior ao Imagen 3

### Abordagens alternativas (em ordem de preferência)

**Opção A — Gemini Flash com geração de imagem (atual)**
```python
# já implementado — testar primeiro
model = genai.GenerativeModel("gemini-2.0-flash-exp")
```

**Opção B — Gemini 2.0 Flash com output de imagem (API atualizada)**
```python
# Se opção A falhar com erro de mime type
response = model.generate_content(
    contents=[prompt, PIL_image],
    generation_config=genai.GenerationConfig(
        response_mime_type="image/png"
    )
)
```

**Opção C — Fallback para composição manual de cor**
```python
# Se Gemini não suportar geração de imagem: 
# aplicar multiplicação de cor via Pillow (sem IA)
# resultado menos realista mas funcional para MVP
from PIL import Image, ImageEnhance
import numpy as np

def apply_color_tint(image: Image.Image, hex_color: str) -> Image.Image:
    """
    Aplica tint de cor via multiplicação de canal.
    Fallback determinístico se Gemini falhar.
    """
    r = int(hex_color[1:3], 16) / 255
    g = int(hex_color[3:5], 16) / 255
    b = int(hex_color[5:7], 16) / 255

    img_array = np.array(image.convert("RGBA")).astype(float)
    # Preservar canal alpha
    alpha = img_array[:, :, 3]
    # Converter para escala de cinza (luminância)
    gray = 0.299 * img_array[:, :, 0] + 0.587 * img_array[:, :, 1] + 0.114 * img_array[:, :, 2]
    # Aplicar cor alvo mantendo luminância
    img_array[:, :, 0] = np.clip(gray * r * 2, 0, 255)
    img_array[:, :, 1] = np.clip(gray * g * 2, 0, 255)
    img_array[:, :, 2] = np.clip(gray * b * 2, 0, 255)
    img_array[:, :, 3] = alpha

    return Image.fromarray(img_array.astype(np.uint8))
```

### Atualizar `backend/app/services/color_variation.py`

O serviço deve ter estrutura com fallback explícito:

```python
def apply_color_variation(
    image_bytes: bytes,
    target_hex: str,
    protected_regions: list[dict],
    output_path: Path,
) -> dict:
    """
    Tenta Gemini primeiro. Se falhar, usa fallback Pillow.
    Registra qual método foi usado no resultado.
    """
    try:
        result = _apply_via_gemini(image_bytes, target_hex, protected_regions, output_path)
        result["method"] = "gemini"
        return result
    except Exception as e:
        logger.warning(f"Gemini falhou ({e}), usando fallback Pillow para {target_hex}")
        result = _apply_via_pillow(image_bytes, target_hex, output_path)
        result["method"] = "pillow_fallback"
        result["cost_cents"] = 0  # fallback é gratuito
        return result


def _apply_via_gemini(image_bytes, target_hex, protected_regions, output_path) -> dict:
    # implementação Gemini atual
    ...

def _apply_via_pillow(image_bytes, target_hex, output_path) -> dict:
    # fallback determinístico
    ...
```

**Registrar método usado** em `generation_jobs.api_used`:
- `"gemini"` → chamou Gemini com sucesso
- `"gemini_fallback_pillow"` → Gemini falhou, usou Pillow
- `cost_cents = 0` para jobs com fallback Pillow

---

## S03-03 — Fase A: POC com 1 Imagem × 1 Cor

### Sequência de comandos para executar via API

Usar `IMAGE_ID_FRENTE` do seed + cor `#696980`.

**Passo 1 — Verificar transparência (deve retornar skipped: true)**
```bash
curl -X POST http://localhost:8002/api/v1/products/{PRODUCT_ID}/images/{IMAGE_ID_FRENTE}/remove-background \
  -H "Authorization: Bearer {TOKEN}"
```
Esperado: `{"data": {"skipped": true, "status": "done"}}`

**Passo 2 — Detectar regiões protegidas (Claude Vision real)**
```bash
curl -X POST http://localhost:8002/api/v1/jobs/detect-protected-regions \
  -H "Authorization: Bearer {TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"product_image_id": "{IMAGE_ID_FRENTE}"}'
```
Esperado: `{"has_protected_regions": false, "regions_count": 0}`
Verificar: `cost_cents` registrado no banco

**Passo 3 — Variação de cor (Gemini real — 1 cor)**
```bash
curl -X POST http://localhost:8002/api/v1/jobs/color-variation \
  -H "Authorization: Bearer {TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "product_image_id": "{IMAGE_ID_FRENTE}",
    "target_colors": ["#696980"],
    "protected_regions": []
  }'
```
Esperado: `{"results": [{"status": "pending_review", ...}]}`

**Critérios de qualidade — Fase A:**
- [ ] Imagem gerada existe em disco
- [ ] Cor aplicada visualmente próxima ao HEX `#696980`
- [ ] Textura da peça preservada (não é cor sólida chapada)
- [ ] Bordas da peça sem halo de cor
- [ ] `method` registrado (`gemini` ou `gemini_fallback_pillow`)
- [ ] `cost_cents` registrado

**Se qualidade for insatisfatória:** ajustar prompt no `color_variation.py` e reprocessar antes de avançar para Fase B.

---

## S03-04 — Fase B: Pipeline Completo (4 Views × 3 Cores)

Só executar após Fase A aprovada.

### Sequência

**Para cada uma das 4 views:**
1. Remoção de fundo → `skipped: true` (todas já transparentes)
2. Detecção de regiões → `has_protected_regions: false`
3. Variação de cor com as 3 cores: `["#696980", "#978b7b", "#9e987d"]`

**Total de jobs de geração:** 4 views × 3 cores = **12 imagens**

**Custo estimado Fase B:**
- Detecção Claude: 4 × ~$0.015 = ~$0.06
- Variação Gemini: 12 × ~$0.03 = ~$0.36
- Total: ~$0.42 USD (~R$ 2,50)

### Script de automação `backend/scripts/run_pipeline_sprint03.py`

```python
"""
Executa pipeline completo para as 4 views com 3 cores.
Ler IDs de backend/scripts/sprint03_ids.txt antes de rodar.
Executar: docker compose exec api python backend/scripts/run_pipeline_sprint03.py
"""
import os
import requests
import json
from pathlib import Path

BASE_URL = "http://localhost:8002/api/v1"
COLORS = ["#696980", "#978b7b", "#9e987d"]
VIEWS = ["frente", "costas", "lat_direita", "lat_esquerda"]

# Ler IDs do arquivo de seed
ids_file = Path("/app/backend/scripts/sprint03_ids.txt")
ids = dict(line.strip().split("=") for line in ids_file.read_text().splitlines())

PRODUCT_ID = ids["PRODUCT_ID"]
IMAGE_IDS = {
    "frente": ids["IMAGE_ID_FRENTE"],
    "costas": ids["IMAGE_ID_COSTAS"],
    "lat_direita": ids["IMAGE_ID_LAT_DIREITA"],
    "lat_esquerda": ids["IMAGE_ID_LAT_ESQUERDA"],
}


def get_token() -> str:
    r = requests.post(f"{BASE_URL}/auth/login", json={
        "email": os.getenv("ADMIN_EMAIL", "admin@confexai.local"),
        "password": os.getenv("ADMIN_PASSWORD", "admin123"),
    })
    return r.json()["data"]["access_token"]


def run_pipeline(token: str):
    headers = {"Authorization": f"Bearer {token}"}
    total_cost = 0
    results = []

    for view, image_id in IMAGE_IDS.items():
        print(f"\n=== Processando: {view} ===")

        # Passo 1: Remoção de fundo
        r = requests.post(
            f"{BASE_URL}/products/{PRODUCT_ID}/images/{image_id}/remove-background",
            headers=headers,
        )
        bg_data = r.json()["data"]
        print(f"  Fundo: {'skipped (já transparente)' if bg_data.get('skipped') else 'removido'}")

        # Passo 2: Detecção de regiões protegidas
        r = requests.post(
            f"{BASE_URL}/jobs/detect-protected-regions",
            json={"product_image_id": image_id},
            headers=headers,
        )
        detect_data = r.json()["data"]
        cost = detect_data.get("cost_cents", 0)
        total_cost += cost
        protected = detect_data.get("protected_regions", [])
        print(f"  Detecção: has_protected={detect_data['has_protected_regions']} | custo: {cost}¢")

        # Passo 3: Variação de cor (3 cores)
        r = requests.post(
            f"{BASE_URL}/jobs/color-variation",
            json={
                "product_image_id": image_id,
                "target_colors": COLORS,
                "protected_regions": protected,
            },
            headers=headers,
        )
        color_data = r.json()["data"]
        for res in color_data["results"]:
            cost = res.get("cost_cents", 0)
            total_cost += cost
            method = res.get("method", "?")
            print(f"  Cor {res['color_hex']}: {res['status']} | método: {method} | custo: {cost}¢")
            results.append(res)

    print(f"\n=== Resumo ===")
    print(f"Total de imagens geradas: {len([r for r in results if r['status'] == 'pending_review'])}/12")
    print(f"Custo total: {total_cost}¢ (~R$ {total_cost * 0.006:.2f})")

    # Salvar resultado
    with open("/app/backend/scripts/sprint03_results.json", "w") as f:
        json.dump({"total_cost_cents": total_cost, "results": results}, f, indent=2)
    print(f"✅ Resultados salvos em backend/scripts/sprint03_results.json")


if __name__ == "__main__":
    token = get_token()
    run_pipeline(token)
```

---

## S03-05 — Export dos Assets Aprovados

Após revisão visual dos resultados:

**Aprovar jobs via API:**
```bash
# Para cada job_id em pending_review:
curl -X POST http://localhost:8002/api/v1/jobs/{JOB_ID}/approve \
  -H "Authorization: Bearer {TOKEN}"
```

**Estrutura esperada de outputs em disco:**
```
backend/uploads/{product_id}/
├── frente.png                    ← original
├── frente_nobg.png               ← se rembg rodou (ou própria frente.png)
├── color_696980_frente.png       ← variação PNG
├── color_696980_frente.jpg       ← variação JPG 1200×1200
├── color_978b7b_frente.png
├── color_978b7b_frente.jpg
├── color_9e987d_frente.png
├── color_9e987d_frente.jpg
├── costas.png
├── color_696980_costas.png
... (12 variações no total)
```

---

## S03-06 — Registro de Custos Reais

Após execução, consultar banco e registrar custos reais:

```sql
-- Executar no banco para ver custo total do sprint
SELECT
    type,
    api_used,
    COUNT(*) as jobs,
    SUM(cost_cents) as total_cents,
    AVG(cost_cents) as avg_cents
FROM generation_jobs
WHERE status IN ('done', 'approved', 'pending_review')
GROUP BY type, api_used
ORDER BY type;
```

Atualizar a skill `confexai-architecture-decisions` com os custos reais observados.

---

## Ordem de Execução

```
S03-01 (seed)
  ↓
S03-02 (ajustar serviço Gemini se necessário)
  ↓
S03-03 (Fase A — POC 1 imagem × 1 cor) → avaliar qualidade
  ↓ (só se Fase A aprovada)
S03-04 (Fase B — 4 views × 3 cores)
  ↓
S03-05 (aprovar e verificar assets em disco)
  ↓
S03-06 (registrar custos reais)
```

---

## Commits Atômicos

```
feat(scripts): add seed and pipeline scripts for sprint 03 integration [S03-01]
fix(color-variation): add Pillow fallback and method tracking for Gemini [S03-02]
docs(costs): update cost estimates with real API data from sprint 03 [S03-06]
```

> Sprints de integração geram menos commits de código — o valor está na validação.

---

## Critérios de Aceite

- [ ] Seed roda sem erros — produto + 4 imagens criados no banco
- [ ] Detecção Claude Vision retorna `has_protected_regions: false` para peça lisa
- [ ] Variação de cor gera imagem visualmente coerente com o HEX alvo
- [ ] Textura da peça preservada (não cor sólida)
- [ ] 12 arquivos de output em disco (PNG + JPG por variação)
- [ ] Custos registrados em `generation_jobs.cost_cents` para todos os jobs
- [ ] `sprint03_results.json` gerado com resumo completo
- [ ] Assets aprovados via endpoint `/approve`

---

## Pontos de Decisão durante o Sprint

| Situação | Ação |
|---|---|
| Gemini retorna erro de `response_mime_type` | Implementar fallback Pillow, documentar limitação |
| Cor gerada muito diferente do HEX | Ajustar prompt, retry com intensidade diferente |
| Cor gerada correta mas textura destruída | Reduzir `guidance_scale`, retry |
| Custo real muito acima da estimativa | Registrar, revisar estimativa SaaS antes de escalar |
| Claude Vision retorna `has_protected_regions: true` para peça lisa | Bug no prompt — corrigir threshold de confiança |
