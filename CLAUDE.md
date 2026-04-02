# ConfexAI — Knowledge Base

## Visão Geral

Plataforma de automação visual para confecção têxtil. Dado uma foto de peça de roupa, gera variações de cor, fundos alternativos, descrições SEO e vídeos UGC.

**Stack:** FastAPI + PostgreSQL + React + Vite + TailwindCSS  
**APIs externas:** Anthropic Claude, Google Gemini, KlingAI  
**Ambiente:** Docker Compose V2 (api: 8002, db: 5435, frontend: 5173)

---

## Estado atual (Sprint 14 — Março 2026)

### Módulos implementados
- Upload de imagens com 4 views (frente, costas, lat_direita, lat_esquerda)
- Remoção de fundo (rembg local + Gemini fallback)
- Detecção de regiões protegidas (estampas/bordados) via Claude Vision
- Variação de cor via Gemini Imagen (google-genai SDK)
- Aprovação/rejeição/arquivamento de resultados (soft delete)
- Export ZIP por imagem, produto e multi-produto
- Histórico completo de execuções com prompt, métricas e custo
- Página de Resultados agrupada por produto com seleção individual
- Descrições SEO via Claude Vision (ML, Shopee, Shopify)
- Rate limiting no endpoint SEO (30s por produto)
- Documentação completa: SPEC.md, ROUTE_REFERENCE.md, ADRs, design tokens

### Módulos pendentes
- Fundo alternativo lifestyle (Gemini)
- Geração de vídeo UGC (KlingAI)
- Multi-tenant / SaaS

---

## Documentação do Projeto

| Arquivo | Conteúdo |
|---|---|
| `docs/SPEC.md` | Fluxos de usuário, critérios de aceite, antipadrões |
| `docs/ROUTE_REFERENCE.md` | Mapa completo de rotas frontend → backend |
| `docs/claude-design-tokens.json` | Paleta, tipografia e tokens de design |
| `docs/decisions/ADRs.md` | 15 decisões arquiteturais formalizadas |
| `docs/PRD_SprintNN_*.md` | PRDs de cada sprint |

**Leitura obrigatória ao iniciar qualquer tarefa:**
```
Read docs/SPEC.md
Read docs/ROUTE_REFERENCE.md
Read .claude/skills/confexai-sprint-workflow/SKILL.md
```

---

## Arquitetura

```
backend/
├── app/
│   ├── api/
│   │   ├── health.py
│   │   ├── auth.py
│   │   ├── products.py    # CRUD + POST/GET /seo
│   │   ├── images.py      # upload, remove-background
│   │   └── jobs.py        # jobs, history, export, archive, color-variation
│   ├── models.py          # ORM SQLAlchemy
│   ├── schemas/           # Pydantic
│   ├── services/
│   │   ├── background_removal.py
│   │   ├── color_variation.py    # Gemini + Pillow fallback
│   │   ├── protected_regions.py  # Claude Vision
│   │   ├── seo_generator.py      # Claude Vision — análise + geração SEO
│   │   └── url_helper.py         # path_to_url() — paths internos → URLs públicas
│   ├── migrations/        # Scripts manuais idempotentes + rollbacks
│   └── main.py            # StaticFiles em /static/uploads, CORS com PATCH
frontend/
├── src/
│   ├── pages/
│   │   ├── Login.jsx
│   │   ├── Produtos.jsx   # Lista + botões Pipeline / Resultados / SEO por produto
│   │   ├── Pipeline.jsx   # Upload 4 views + cores + execução + redirect
│   │   ├── Resultados.jsx # Agrupado por produto, archive, download, seleção individual
│   │   ├── Historico.jsx  # Rastreabilidade completa com prompt e métricas
│   │   └── SEO.jsx        # Geração SEO por plataforma com copy buttons
│   ├── components/
│   │   ├── Layout.jsx     # Sidebar: Produtos, Resultados, Histórico, Novo Pipeline
│   │   └── Toast.jsx      # Notificações globais (success, error, warning, info)
│   └── services/api.js    # Todas as chamadas à API com axios
```

---

## Banco de Dados

### Tabelas principais

| Tabela | Descrição |
|---|---|
| `products` | Produtos cadastrados (soft delete via `is_active`) |
| `product_images` | Imagens por produto e view (original, color_variant) |
| `generation_jobs` | Jobs com status, custo, prompt, modelo, tempo, rastreabilidade |
| `job_api_logs` | Request/response bruto de cada chamada de IA (auditoria) |
| `seo_descriptions` | Descrições SEO por produto e plataforma |

### Campos críticos em `generation_jobs`

```
type:            background_removal | protected_region_detection | color_variation | seo_description | video_ugc
status:          pending | processing | done | failed | pending_review | approved | rejected
is_archived:     bool (soft delete visual)
deleted_at:      timestamp (soft delete permanente — não aparece na UI, fica no banco)
prompt_used:     text (prompt exato enviado à IA)
model_used:      varchar (ex: gemini-2.0-flash-exp)
duration_ms:     int (tempo de execução)
input_image_url: varchar (/static/uploads/...)
cost_cents:      int
fallback_reason: text (preenchido se Pillow fallback ativou)
```

### Campos críticos em `seo_descriptions`

```
platform:    mercadolivre | shopee | shopify
title:       varchar(200)
description: text
tags:        text (JSON array serializado)
is_approved: bool
updated_at:  timestamp (atualizado a cada regeneração)
```

### Índices importantes

```
ix_generation_jobs_created_at        — ORDER BY created_at DESC
ix_generation_jobs_is_archived       — filter is_archived = false
ix_job_api_logs_job_id               — JOIN job_api_logs
ix_product_images_product_id         — JOIN product_images
ix_seo_descriptions_product_platform — WHERE product_id + platform
ix_generation_jobs_deleted_at        — WHERE deleted_at IS NULL (partial index)
```

---

## Variáveis de Ambiente

```env
DATABASE_URL=postgresql://confexai:confexai@db:5432/confexai_db
DATABASE_TEST_URL=postgresql://confexai:confexai@db:5432/confexai_test_db
SECRET_KEY=troque-por-uma-chave-segura-de-32-chars
ANTHROPIC_API_KEY=
GOOGLE_API_KEY=
KLING_ACCESS_KEY=
KLING_SECRET_KEY=
ADMIN_EMAIL=admin@confexai.local
ADMIN_PASSWORD_HASH=
UPLOAD_DIR=/app/examples/uploads
MAX_IMAGE_SIZE_MB=20
DEFAULT_OUTPUT_FORMAT=jpg
DEFAULT_OUTPUT_RESOLUTION=1200
```

---

## Decisões Arquiteturais Chave

Ver `docs/decisions/ADRs.md` para o registro completo (15 ADRs).

**Resumo:**
- **React** no frontend — estado complexo de pipeline (ADR-001)
- **rembg local** como motor primário de remoção de fundo (ADR-005)
- **google-genai SDK** — usa `response_modalities`, não `response_mime_type` (ADR-006)
- **Pillow fallback** automático se Gemini falhar — rastreado via `fallback_reason` (ADR-007)
- **Sem Celery no MVP** — jobs síncronos (ADR-008)
- **Soft delete universal** — `is_archived` / `is_active`, nunca `db.delete()` (ADR-003)
- **Static files** em `/static/uploads` sem autenticação (ADR-009)
- **CORS inclui PATCH** — necessário para archive/unarchive (ADR-010)
- **Nome de arquivo com view** — `original_{view}.{ext}` evita sobrescrita (ADR-011)
- **Literal types** no Pydantic para campos com valores fixos (ADR-012)
- **dangerouslySetInnerHTML proibido** com conteúdo externo (ADR-013)
- **Auditoria obrigatória antes do commit** (ADR-015)

---

## Comandos Úteis

```bash
# Subir ambiente
docker compose up -d

# Rodar testes
docker compose exec api python -m pytest tests/ -v

# Rodar migration
docker compose exec api python backend/app/migrations/migrate_sprint_NN.py

# Ver logs da API
docker compose logs api --tail=30

# Acessar banco
docker compose exec db psql -U confexai -d confexai_db
```

---

## Workflow de Sprint (Resumo)

1. Inspeção → 2. Análise → 3. Aprovação → 4. Implementação
5. Testes (0 failed) → **5.5. Auditoria sgp-sprint-review (ANTES do commit)**
6. Commits atômicos → 7. Push → 8. CLAUDE.md atualizado

---

## Antipadrões — Nunca Fazer

```
❌ db.delete(entity)                          → soft delete obrigatório
❌ raise HTTPException(500, detail=str(e))    → expõe internos
❌ API externa sem mock em teste              → custo real + flakiness
❌ N+1 query em loop                          → prefetch com .in_()
❌ response_mime_type: "image/png"            → HTTP 400 no Gemini
❌ original.png sem view no nome              → sobrescreve outras views
❌ dangerouslySetInnerHTML com banco/IA       → XSS
❌ CORS sem PATCH                             → archive quebra silenciosamente
❌ platforms: list[str] no Pydantic           → aceita valores inválidos
❌ Commitar antes da auditoria               → bloqueantes vão para produção
```

---

## Sprints

| Sprint | Entrega | Testes |
|---|---|---|
| 01 | Setup, auth, produtos, upload | 18 |
| 02 | Remoção de fundo, detecção, variação de cor, aprovação | 34 |
| 03 | Integração real Gemini + Anthropic, seed scripts | 34 |
| 04 | Frontend React (login, produtos, pipeline) | 34 |
| 05 | Static serving, preview de imagem, URL públicas | 38 |
| 06 | UX: toasts, progress steps, modal de confirmação, resultados | 38 |
| 07 | Resultados definitivo: archive, download ZIP, multi-seleção | 38 |
| 08 | Histórico completo: prompt, métricas, job_api_logs | 44 |
| 09 | Dívida técnica: índices, N+1, rollbacks, docs | 50 |
| 10 | Fix bug de view no upload — arquivos distintos por view | 55 |
| 11 | Validação pipeline completo — 4 views × 3 cores end-to-end | 55 |
| 12 | Descrições SEO — Claude Vision gera título/descrição para ML, Shopee, Shopify | 65 |
| 13 | Backlog SEO — updated_at, índice composto, rate limiting no endpoint SEO | 68 |
| 14 | Documentação — SPEC.md, ROUTE_REFERENCE, design tokens, ADRs | 68 |
| 15 | UI/UX Virada 360 — skeleton, hierarquia visual, soft delete (deleted_at) | 78 |
| 16 | PDCA pipeline de cor — colisão de arquivos, job_short_id, Gemini reativado | 84 |
