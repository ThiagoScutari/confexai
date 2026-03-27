# ConfexAI — Architecture Decision Records (ADRs)

**Localização:** `docs/decisions/`  
**Formato:** ADR numerado, imutável após aprovado. Supersedidos são marcados, não deletados.  
**Versão:** 1.0 — Sprint 14

---

## ADR-001 — React no Frontend (não HTML/JS Vanilla)

**Status:** Aprovado — Sprint 01  
**Contexto:** Sistema tem estado complexo: fila de imagens, progresso por etapa, múltiplas variações simultâneas, preview de máscara, player de resultado.  
**Decisão:** React + Vite + TailwindCSS.  
**Alternativas rejeitadas:** HTML/JS Vanilla, Alpine.js, HTMX, Vue.  
**Consequências:** Build step necessário; `node_modules` deve estar na imagem Docker, não apenas no volume host (aprendizado do Sprint 04).  
**Regra derivada:** Nunca sugerir migração para Vanilla JS ou Alpine. Estado de pipeline não é gerenciável sem framework reativo.

---

## ADR-002 — Monolito FastAPI, Não Microserviços

**Status:** Aprovado — Sprint 01  
**Contexto:** MVP para DRX Têxtil. Volume pequeno, equipe de 1 desenvolvedor, VPS única.  
**Decisão:** Monolito FastAPI com routers modulares.  
**Estrutura:**
- `app/main.py` — bootstrap (≤ 200 linhas)
- `app/api/` — routers por domínio
- `app/services/` — lógica de negócio stateless
- `app/models.py` — ORM SQLAlchemy
- `app/schemas/` — Pydantic
**Alternativas rejeitadas:** Microserviços, message queues, event sourcing, CQRS.  
**Regra derivada:** Nunca propor separar em serviços independentes no MVP.

---

## ADR-003 — Soft Delete Universal

**Status:** Aprovado — Sprint 01  
**Contexto:** Rastreabilidade e possibilidade de restore são requisitos implícitos em sistema de produção têxtil.  
**Decisão:** Nunca hard delete em entidades de negócio. Usar `is_active` ou `is_archived`.  
**Exceções:** Logs temporários, cache, dados de sessão — podem ser deletados fisicamente.  
**Regra derivada:** Qualquer `db.delete(entity)` em entidade de negócio é bug crítico.

---

## ADR-004 — Migrações Manuais, Não Alembic

**Status:** Aprovado — Sprint 01  
**Contexto:** Ambiente sem CD automatizado. Cada migração é revisada e aplicada manualmente.  
**Decisão:** Scripts Python idempotentes em `backend/app/migrations/`.  
**Padrão:**
```
migrate_sprint_NN.py   ← aplica mudança
rollback_sprint_NN.py  ← desfaz mudança
```
**Regra derivada:** Toda migration deve ter rollback correspondente. Toda migration deve ser idempotente (verificar existência antes de criar).

---

## ADR-005 — rembg Local como Motor Primário de Remoção de Fundo

**Status:** Aprovado — Sprint 02  
**Contexto:** Volume do MVP não justifica custo de API paga por imagem.  
**Decisão:** `rembg` (Python, gratuito, local) como motor primário. Gemini Vision como fallback.  
**Threshold:** Se confidence do rembg < 0.85, acionar fallback.  
**Alternativas rejeitadas:** Remove.bg (pago por imagem).  
**Regra derivada:** Nunca sugerir Remove.bg como substituto primário.

---

## ADR-006 — google-genai SDK (Não google-generativeai Legado)

**Status:** Aprovado — Sprint 03 (hotfix após erro 400)  
**Contexto:** `google-generativeai` não suporta `response_mime_type: "image/png"`. Retorna HTTP 400.  
**Decisão:** Usar `google-genai` (GA desde maio 2025) com `response_modalities=["IMAGE", "TEXT"]`.  
**Código correto:**
```python
from google import genai
from google.genai import types
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
response = client.models.generate_content(
    model="gemini-2.0-flash-exp",
    contents=[...],
    config=types.GenerateContentConfig(
        response_modalities=["IMAGE", "TEXT"],
    ),
)
```
**Regra derivada:** Nunca usar `response_mime_type: "image/png"` — causa erro 400 silencioso.

---

## ADR-007 — Pillow Fallback Automático para Variação de Cor

**Status:** Aprovado — Sprint 03  
**Contexto:** Gemini pode falhar por quota, timeout ou modelo indisponível. O pipeline não pode parar.  
**Decisão:** `_apply_via_gemini()` com try/except, fallback para `_apply_via_pillow()`.  
**Rastreabilidade:** `method: "gemini"` ou `"pillow_fallback"` registrado no resultado. `fallback_reason` no job.  
**Custo do fallback:** `cost_cents = 0` (Pillow é local e gratuito).

---

## ADR-008 — Sem Fila Assíncrona no MVP

**Status:** Aprovado — Sprint 01, validado Sprint 03  
**Contexto:** Volume do MVP (~10 SKUs × 5 cores = 50 gerações/ciclo). Celery + Redis seria overkill.  
**Decisão:** Jobs síncronos no MVP. Tabela `generation_jobs` prepara migração futura sem retrabalho.  
**Migração futura:** Substituir worker thread por Celery worker + Redis broker sem mudar modelo de dados.  
**Regra derivada:** Nunca adicionar Celery no MVP. Reavaliar quando volume > 500 jobs/dia.

---

## ADR-009 — Static Files Servidos pelo FastAPI

**Status:** Aprovado — Sprint 05  
**Contexto:** Imagens geradas precisam ser acessíveis pelo browser sem autenticação (exibição em `<img src>`).  
**Decisão:** `StaticFiles` do FastAPI montado em `/static/uploads` apontando para `UPLOAD_DIR`.  
**Código:**
```python
app.mount("/static/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
```
**Dependência:** `aiofiles` no requirements.txt.  
**Regra derivada:** Nunca adicionar token de auth em requests de imagem — static files são públicos por design.

---

## ADR-010 — CORS Deve Incluir PATCH

**Status:** Aprovado — Sprint 07 (hotfix após bug de archive)  
**Contexto:** `PATCH` ausente no `allow_methods` causava falha silenciosa no preflight, impedindo archive/unarchive.  
**Decisão:** CORS deve incluir explicitamente: `["GET", "POST", "PUT", "DELETE", "PATCH"]`.  
**Regra derivada:** Ao adicionar qualquer endpoint com método HTTP não-padrão, verificar se está no CORS.

---

## ADR-011 — Nome de Arquivo com View no Upload

**Status:** Aprovado — Sprint 10 (bug crítico)  
**Contexto:** Nome fixo `original.png` causava sobrescrita — todas as views processavam a mesma imagem física.  
**Decisão:** `original_{view}.{ext}` para uploads com view. `original.{ext}` para uploads sem view (compatibilidade legada).  
**Código:**
```python
view_suffix = f"_{view}" if view else ""
file_path = product_dir / f"original{view_suffix}{Path(file.filename).suffix}"
```
**Regra derivada:** Nunca usar nome fixo de arquivo para recursos que podem ter múltiplas variantes por produto.

---

## ADR-012 — Validação de Enums com Pydantic Literal

**Status:** Aprovado — Sprint 12 (hotfix após auditoria)  
**Contexto:** Campo `platforms` aceitava qualquer string, incluindo `"instagram"`, que causava exceção não tratada internamente.  
**Decisão:** Usar `Literal` do Python para todo campo com valores fixos.  
**Exemplo:**
```python
from typing import Literal
PlatformType = Literal["mercadolivre", "shopee", "shopify"]
platforms: list[PlatformType] = ["mercadolivre", "shopee", "shopify"]
```
**Aplica-se a:** `platforms`, `view`, `type` de job, `status`.  
**Regra derivada:** Todo campo com enum deve usar `Literal` — nunca `str` livre para valores fixos.

---

## ADR-013 — dangerouslySetInnerHTML é Proibido com Conteúdo Externo

**Status:** Aprovado — Sprint 12 (bloqueante na auditoria)  
**Contexto:** `dangerouslySetInnerHTML` com conteúdo do banco/IA permite XSS se alguém injetar HTML via API.  
**Decisão:** Usar renderização segura (`whitespace-pre-wrap`) para todo conteúdo externo. Se HTML for necessário (ex: Shopify), sanitizar com DOMPurify antes de renderizar.  
**Regra derivada:** Qualquer `dangerouslySetInnerHTML` com conteúdo não-literal é bloqueante na auditoria.

---

## ADR-014 — Rate Limiting In-Memory para MVP

**Status:** Aprovado — Sprint 13  
**Contexto:** Endpoints custosos (SEO, variação de cor) podem gerar custo descontrolado com clique duplo ou abuso.  
**Decisão:** Rate limit via dict Python em memória para MVP. Redis quando virar SaaS.  
**Padrão:**
```python
_rate_limit: dict[str, datetime] = {}
LIMIT_SECONDS = 30

def _check_rate_limit(user_key: str, resource_id: str) -> None:
    key = f"{user_key}:{resource_id}"
    now = datetime.utcnow()
    last = _rate_limit.get(key)
    if last and (now - last).total_seconds() < LIMIT_SECONDS:
        remaining = LIMIT_SECONDS - int((now - last).total_seconds())
        raise HTTPException(429, detail=f"Aguarde {remaining}s.")
    _rate_limit[key] = now
```
**Limitação:** Não persiste entre restarts do container. Aceitável no MVP single-user.

---

## ADR-015 — Auditoria Obrigatória Antes do Commit

**Status:** Aprovado — Sprint 12 (após bloqueante XSS passar para produção)  
**Contexto:** Bug de XSS (`dangerouslySetInnerHTML`) foi commitado sem auditoria prévia.  
**Decisão:** Skill `sgp-sprint-review` deve rodar obrigatoriamente após pytest verde e ANTES de qualquer commit.  
**Veredicto bloqueante:** 🔴 = corrigir antes do commit. ⚠️ = commitar com itens de backlog registrados.  
**Regra derivada:** Nenhum sprint é encerrado sem auditoria aprovada. Esta regra está na skill `confexai-sprint-workflow` (Passo 5.5).
