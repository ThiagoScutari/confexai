# PRD — Sprint 16: Correção do Pipeline de Variação de Cor

**Status:** Aprovação Pendente  
**Origem:** Auditoria de resultado de pipeline — imagens com efeito "negativo", perda de detalhes e identidade da peça  
**Data:** 2026-04-01  
**Objetivo:** Corrigir os 3 defeitos críticos do pipeline de variação de cor para que o resultado seja fiel à peça original.

---

## Sumário Executivo

| ID | Severidade | Descrição | Esforço |
|---|---|---|---|
| S16-01 | 🔴 Crítico | Pós-processamento: restaurar alpha da original sobre output do Gemini | Médio |
| S16-02 | 🔴 Crítico | Pós-processamento: restaurar resolução original (resize para dimensões da entrada) | Pequeno |
| S16-03 | 🔴 Crítico | Melhorar prompt para forçar preservação de estrutura e detalhes | Médio |
| S16-04 | 🟡 Médio | Registrar métricas de qualidade (correlação de bordas) para detecção automática de regressão | Médio |
| S16-05 | 🟡 Médio | Fallback Pillow: corrigir algoritmo de tint para resultado mais realista | Pequeno |

---

## Diagnóstico — O Que Está Errado

### Relatório de Execução (2026-04-01)

Pipeline executado sobre produto `5c7397bc` (Blusa), view `frente`, cores alvo `#978B7B` e `#9E987D`.

| Problema | Evidência | Impacto |
|---|---|---|
| **Peça devolvida ≠ peça enviada** | Correlação de bordas = 0.19 (< 0.50 = imagem diferente). Gemini gera peça NOVA, não edita a original. | Produto anunciado seria diferente do real. Inaceitável para e-commerce. |
| **Fundo transparente vira preto** | Gemini retorna RGB sem alpha. Original é RGBA com 49.9% transparência. | JPG final mostra peça em retângulo preto no canvas branco. |
| **Cor escura / efeito "negativo"** | Target #978B7B = R151, output R=77 (51% do esperado). Peça fica mais escura que a original. | Visual de filme negativo — dessaturado, sem vida. |
| **Resolução reduzida em 64%** | Original 1414x2000, Gemini retorna 864x1184. | Perda irrecuperável de detalhes, textura, costuras. |

### Causa Raiz Técnica

`generate_content` com `response_modalities=["IMAGE"]` é uma **API de geração**, não de edição. O modelo usa a imagem de entrada como inspiração e gera uma imagem nova. Não existe pixel-editing no Gemini via API key simples.

A API de edição real (`edit_image` com Imagen 3.0) requer **Vertex AI** (GCP project + service account) e está deprecated para junho/2026. A alternativa `imagen-4` **não suporta edição** — apenas geração.

### Decisão Arquitetural

Migrar para Vertex AI é investimento de infraestrutura desproporcional para o MVP. A estratégia é **manter `generate_content`** com Gemini e adicionar **pós-processamento robusto** que:

1. Força a preservação da transparência (alpha da original)
2. Restaura a resolução original
3. Melhora o prompt para minimizar alucinação de detalhes
4. Detecta automaticamente quando o resultado é muito diferente da original

---

## S16-01 — Restaurar Alpha Channel da Original

### Problema
Gemini retorna imagem RGB sem canal alpha. O fundo que era transparente vira preto sólido.

### Implementação

**Arquivo:** `backend/app/services/color_variation.py` — função `_apply_via_gemini`

Após receber `result_bytes` do Gemini e antes de chamar `_save_result`, adicionar pós-processamento:

```python
def _restore_alpha(original_bytes: bytes, gemini_bytes: bytes) -> bytes:
    """
    Aplica o canal alpha da imagem original sobre o output do Gemini.
    Isso restaura a transparência do fundo que o Gemini destruiu.
    """
    original = Image.open(io.BytesIO(original_bytes)).convert("RGBA")
    gemini_img = Image.open(io.BytesIO(gemini_bytes)).convert("RGBA")

    # Redimensionar Gemini output para o tamanho da original
    if gemini_img.size != original.size:
        gemini_img = gemini_img.resize(original.size, Image.LANCZOS)

    # Extrair canal alpha da original
    _, _, _, original_alpha = original.split()

    # Aplicar alpha da original sobre o resultado do Gemini
    gemini_img.putalpha(original_alpha)

    buf = io.BytesIO()
    gemini_img.save(buf, format="PNG")
    return buf.getvalue()
```

### Critérios de Aceite
- [ ] Output PNG tem canal alpha idêntico à imagem original
- [ ] Fundo é transparente (não preto) no PNG
- [ ] JPG mostra peça sobre fundo branco limpo, sem retângulo preto

---

## S16-02 — Restaurar Resolução Original

### Problema
Gemini retorna imagens em resolução menor (864x1184 vs 1414x2000). Perda de 63.8% dos pixels.

### Implementação
A função `_restore_alpha` já inclui o resize. Adicionalmente, `_save_result` deve usar as dimensões **da imagem original**, não da imagem recebida do Gemini:

```python
# Em _apply_via_gemini, ANTES de _save_result:
result_bytes = _restore_alpha(image_bytes, result_bytes)

# _save_result já recebe width/height da original — manter isso
result = _save_result(result_bytes, output_path, width, height)
```

### Critérios de Aceite
- [ ] Output PNG tem as mesmas dimensões da imagem original de entrada
- [ ] Thumbnailing para JPG 1200x1200 usa a versão full-res, não a versão reduzida do Gemini

---

## S16-03 — Melhorar Prompt de Variação de Cor

### Problema
Prompt atual é genérico. O modelo interpreta como "gere uma roupa parecida com esta cor" em vez de "mude apenas a cor desta peça".

### Prompt Atual (problemático)
```
Recolor this clothing item to the color {color_hex}.

Rules:
- Apply the new color uniformly to the entire garment fabric
- Preserve ALL fabric texture, weave pattern, natural folds, and shadows
- Maintain realistic fabric shading and highlights appropriate for this color
- Keep the result looking like a real product photograph, not an illustration
- Do NOT add any new design elements
- Do NOT change the garment shape or silhouette
- The background must remain fully transparent
```

### Prompt Proposto

```python
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
```

### Mudanças Chave
- **"This is the SAME garment"** — instrução explícita de que é a mesma peça
- **"every structural detail: seams, buttons, collar..."** — lista concreta de o que preservar
- **"fabric dye, not overlay"** — evita que o modelo aplique filtro de cor
- **"Shadowed areas should be darker shade"** — guia realismo de iluminação
- **"highest possible resolution"** — tenta minimizar redução de resolução

### Config Proposta
```python
config=types.GenerateContentConfig(
    response_modalities=["IMAGE"],  # Sem TEXT — output mais limpo
)
```

### Critérios de Aceite
- [ ] Correlação de bordas entre original e resultado > 0.50 (era 0.19)
- [ ] Cor média dos pixels da roupa está dentro de ±30% do target hex
- [ ] Visual aprovado pelo operador em 3 amostras

---

## S16-04 — Métricas de Qualidade Automáticas

### Problema
Não há como detectar automaticamente quando o Gemini retorna uma imagem ruim. O operador só descobre ao visualizar.

### Implementação

Adicionar ao resultado do job campos de qualidade calculados no pós-processamento:

```python
def _compute_quality_metrics(original_bytes: bytes, result_bytes: bytes, target_hex: str) -> dict:
    """Calcula métricas de qualidade para o resultado da variação de cor."""
    from PIL import ImageFilter

    original = Image.open(io.BytesIO(original_bytes)).convert("RGBA")
    result = Image.open(io.BytesIO(result_bytes)).convert("RGBA")

    # Resize para comparação
    if result.size != original.size:
        result = result.resize(original.size, Image.LANCZOS)

    orig_arr = np.array(original)
    result_arr = np.array(result)

    # Máscara de pixels da roupa (alpha > 128)
    mask = orig_arr[:, :, 3] > 128

    # 1. Correlação de bordas (preservação de estrutura)
    orig_gray = Image.fromarray(
        (0.299 * orig_arr[:,:,0] + 0.587 * orig_arr[:,:,1] + 0.114 * orig_arr[:,:,2]).astype(np.uint8)
    )
    result_gray = Image.fromarray(
        (0.299 * result_arr[:,:,0] + 0.587 * result_arr[:,:,1] + 0.114 * result_arr[:,:,2]).astype(np.uint8)
    )
    orig_edges = np.array(orig_gray.filter(ImageFilter.FIND_EDGES))
    result_edges = np.array(result_gray.filter(ImageFilter.FIND_EDGES))

    oe = orig_edges[mask].astype(float)
    re = result_edges[mask].astype(float)
    edge_correlation = float(np.corrcoef(oe, re)[0, 1]) if len(oe) > 0 else 0.0

    # 2. Precisão de cor (distância do target)
    target_r = int(target_hex[1:3], 16)
    target_g = int(target_hex[3:5], 16)
    target_b = int(target_hex[5:7], 16)

    result_r = float(result_arr[:,:,0][mask].mean())
    result_g = float(result_arr[:,:,1][mask].mean())
    result_b = float(result_arr[:,:,2][mask].mean())

    color_distance = ((result_r - target_r)**2 + (result_g - target_g)**2 + (result_b - target_b)**2) ** 0.5

    return {
        "edge_correlation": round(edge_correlation, 4),
        "color_distance": round(color_distance, 1),
        "target_hex": target_hex,
        "result_mean_rgb": [round(result_r), round(result_g), round(result_b)],
        "quality_warning": edge_correlation < 0.40 or color_distance > 100,
    }
```

### Campos Novos em `generation_jobs.result` (JSON)

```json
{
  "quality_metrics": {
    "edge_correlation": 0.62,
    "color_distance": 45.2,
    "target_hex": "#978B7B",
    "result_mean_rgb": [138, 127, 112],
    "quality_warning": false
  }
}
```

### Frontend — Badge de Warning

Se `quality_warning == true`, mostrar badge amarelo no card de resultado:
```jsx
{job.result?.quality_metrics?.quality_warning && (
  <span className="absolute top-2 left-2 text-xs bg-amber-500/20 text-amber-400 px-1.5 py-0.5 rounded font-mono z-10">
    Qualidade baixa
  </span>
)}
```

### Critérios de Aceite
- [ ] `edge_correlation` e `color_distance` calculados e salvos no result JSON de todo job Gemini
- [ ] `quality_warning` flag presente quando métricas abaixo do limiar
- [ ] Badge visível no card quando warning ativo

---

## S16-05 — Melhorar Fallback Pillow

### Problema
O fallback Pillow usa multiplicação simples `gray * r * 2` que produz cores lavadas e pouco realistas. A fórmula atual em [color_variation.py:162](backend/app/services/color_variation.py#L162):

```python
img_array[:, :, 0] = np.clip(gray * r * 2, 0, 255)
```

O multiplicador `* 2` é arbitrário e causa clipping em cores claras.

### Implementação — Color Transfer via LAB Space

```python
def _apply_via_pillow(image_bytes, target_hex, output_path):
    """Fallback: aplica cor via transferência no espaço LAB."""
    from skimage import color as skcolor

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

    # Mask da roupa
    garment_mask = alpha > 128

    # Transferir crominância (a, b) do target, preservar luminância (L) da original
    lab[:, :, 1][garment_mask] = target_lab[1]  # a (green-red)
    lab[:, :, 2][garment_mask] = target_lab[2]  # b (blue-yellow)

    # Ajustar luminância proporcionalmente
    if garment_mask.any():
        orig_L_mean = lab[:, :, 0][garment_mask].mean()
        target_L = target_lab[0]
        L_ratio = target_L / (orig_L_mean + 1e-6)
        lab[:, :, 0][garment_mask] = np.clip(lab[:, :, 0][garment_mask] * L_ratio, 0, 100)

    # Converter de volta para RGB
    rgb_result = np.clip(skcolor.lab2rgb(lab) * 255, 0, 255).astype(np.uint8)

    # Restaurar alpha
    result_arr = np.dstack([rgb_result, alpha.astype(np.uint8)])
    result_img = Image.fromarray(result_arr)

    buf = io.BytesIO()
    result_img.save(buf, format="PNG")
    ...
```

### Critérios de Aceite
- [ ] Cor do fallback visualmente mais próxima do target que a versão atual
- [ ] Sombras e highlights preservados (luminância relativa mantida)
- [ ] Sem clipping (pixels brancos queimados) em cores claras

### Nota
Se `scikit-image` não estiver no `requirements.txt`, adicionar. Alternativa: implementar conversão RGB→LAB manualmente com numpy.

---

## Ordem de Execução

```
S16-03 — Melhorar prompt (menor risco, maior impacto imediato)
  ↓
S16-01 — Restaurar alpha channel (pós-processamento)
  ↓
S16-02 — Restaurar resolução original (junto com S16-01)
  ↓
S16-04 — Métricas de qualidade
  ↓
S16-05 — Melhorar fallback Pillow
  ↓
Testes manuais com 3 peças × 3 cores
  ↓
Auditoria sgp-sprint-review
  ↓
Commits atômicos
```

---

## Testes

### `backend/tests/test_color_quality.py`

```python
def test_restore_alpha_preserva_transparencia():
    """Output deve ter mesmo canal alpha que a original."""

def test_restore_alpha_mantem_resolucao_original():
    """Output deve ter mesmas dimensões que a original."""

def test_quality_metrics_detecta_imagem_ruim():
    """edge_correlation < 0.40 deve ativar quality_warning."""

def test_quality_metrics_aprova_imagem_boa():
    """edge_correlation > 0.50 e color_distance < 80 não deve ativar warning."""

def test_pillow_fallback_cor_proxima_do_target():
    """Média RGB do resultado Pillow deve estar dentro de ±30% do target."""

def test_pillow_fallback_preserva_alpha():
    """Pixels transparentes da original devem permanecer transparentes no fallback."""
```

---

## Commits Atômicos

```
prompt(color): improve color variation prompt for structure preservation [S16-03]
feat(color): restore alpha channel and resolution from original after Gemini [S16-01/02]
feat(color): add quality metrics — edge correlation and color distance [S16-04]
feat(color): improve Pillow fallback with LAB color transfer [S16-05]
feat(frontend): show quality warning badge on low-quality results [S16-04]
test(sprint16): add 6 tests for color quality and alpha restoration [S16]
```

---

## Critérios de Aceite

- [ ] Imagem de saída é a MESMA peça da entrada (correlação de bordas > 0.50)
- [ ] Fundo transparente preservado no PNG, fundo branco limpo no JPG
- [ ] Resolução do output = resolução da imagem original
- [ ] Cor aplicada dentro de ±30% do target hex (color_distance < 80)
- [ ] Métricas de qualidade salvas no result JSON de cada job
- [ ] Badge "Qualidade baixa" visível quando métricas abaixo do limiar
- [ ] Fallback Pillow produz resultado visivelmente melhor que o atual
- [ ] `pytest tests/ -v` → **84+ passed, 0 failed**
- [ ] Auditoria `sgp-sprint-review` aprovada
- [ ] Teste visual: 3 peças × 3 cores aprovadas pelo operador

---

## Riscos e Limitações

| Risco | Mitigação |
|---|---|
| Gemini continua gerando peça diferente mesmo com prompt melhor | S16-04 detecta automaticamente + operador pode rejeitar |
| `scikit-image` adiciona dependência ao container | Verificar tamanho do image. Se muito pesado, implementar LAB via numpy |
| Resize com LANCZOS pode borrar detalhes finos | Aceitável para MVP — resolução original do Gemini já é mais baixa |
| Modelo `gemini-2.5-flash-image` tem teto de ~1024px | Sem solução sem Vertex AI. Pós-processamento restaura dimensões mas não detalhes sub-pixel |

---

## Decisão Futura — Vertex AI

Se após S16 os resultados ainda não forem satisfatórios, a próxima opção é migrar para **Vertex AI** com `edit_image` + `imagen-3.0-capability-001` (mask-based editing real). Isso requer:

- GCP project com billing
- Service account + credenciais
- Variáveis: `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`
- Nota: `imagen-3.0-capability-001` será descontinuado em junho/2026

Essa decisão deve ser tomada **após** validar os resultados da Sprint 16. Se o pós-processamento + prompt melhorado resolverem 80%+ dos casos, Vertex AI pode ser adiado.
