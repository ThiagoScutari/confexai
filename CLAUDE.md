# ConfexAI — Knowledge Base

## Visão Geral

Plataforma de automação visual para confecção têxtil. Dado uma foto de peça de roupa, gera variações de cor, fundos alternativos, descrições SEO e vídeos UGC.

**Stack:** FastAPI + PostgreSQL + React + Vite + TailwindCSS
**APIs externas:** Anthropic Claude, Google Gemini, KlingAI
**Ambiente:** Docker Compose (api: 8002, db: 5435, frontend: 5173)

---

## Estado atual (Sprint 08 — Março 2026)

### Módulos implementados
- Upload de imagens com 4 views (frente, costas, lat_direita, lat_esquerda)
- Remoção de fundo (rembg local + Gemini fallback)
- Detecção de regiões protegidas (estampas/bordados) via Claude Vision
- Variação de cor via Gemini Imagen (google-genai SDK)
- Aprovação/rejeição/arquivamento de resultados
- Export ZIP por produto e multi-produto
- Histórico completo de execuções com prompt, métricas e custo
- Página de Resultados agrupada por produto

### Módulos pendentes
- Descrições SEO (Claude)
- Fundo alternativo lifestyle (Gemini)
- Geração de vídeo UGC (KlingAI)
- Multi-tenant / SaaS

---

## Arquitetura

```
backend/
├── app/
│   ├── api/          # Routers FastAPI
│   │   ├── health.py
│   │   ├── auth.py
│   │   ├── products.py
│   │   ├── images.py
│   │   └── jobs.py   # jobs, history, export, archive
│   ├── models.py     # ORM SQLAlchemy
│   ├── schemas/      # Pydantic
│   ├── services/
│   │   ├── background_removal.py
│   │   ├── color_variation.py   # Gemini + Pillow fallback
│   │   ├── protected_regions.py # Claude Vision
│   │   └── url_helper.py
│   ├── migrations/   # Scripts manuais idempotentes
│   └── main.py       # StaticFiles em /static/uploads
frontend/
├── src/
│   ├── pages/
│   │   ├── Login.jsx
│   │   ├── Produtos.jsx
│   │   ├── Pipeline.jsx   # Upload + geração + revisão
│   │   ├── Resultados.jsx # Agrupado por produto, archive, download
│   │   └── Historico.jsx  # Rastreabilidade completa
│   ├── components/
│   │   ├── Layout.jsx     # Sidebar: Produtos, Resultados, Histórico, Novo Pipeline
│   │   └── Toast.jsx
│   └── services/api.js
```

---

## Banco de Dados

### Tabelas principais
- `products` — produtos cadastrados
- `product_images` — imagens por produto e view
- `generation_jobs` — jobs com status, custo, prompt, modelo, tempo
- `job_api_logs` — request/response bruto de cada chamada de IA
- `seo_descriptions` — (futuro) descrições SEO por plataforma

### Campos críticos em generation_jobs
```
type: background_removal | protected_region_detection | color_variation | seo_description | video_ugc
status: pending | processing | done | failed | pending_review | approved | rejected
is_archived: bool (soft delete)
prompt_used: text
model_used: varchar
duration_ms: int
input_image_url: varchar (/static/uploads/...)
cost_cents: int
```

---

## Variáveis de Ambiente

```env
DATABASE_URL=postgresql://confexai:confexai@db:5432/confexai_db
DATABASE_TEST_URL=postgresql://confexai:confexai@db:5432/confexai_test_db
SECRET_KEY=
ANTHROPIC_API_KEY=
GOOGLE_API_KEY=
KLING_ACCESS_KEY=
KLING_SECRET_KEY=
ADMIN_EMAIL=admin@confexai.local
UPLOAD_DIR=/app/examples/uploads
MAX_IMAGE_SIZE_MB=20
```

---

## Decisões Arquiteturais Chave

- **React** no frontend (não HTML/JS Vanilla) — estado complexo de pipeline
- **rembg local** como motor primário de remoção de fundo (gratuito)
- **google-genai SDK** (não google-generativeai legado) para Gemini
- **Pillow fallback** automático se Gemini falhar
- **Sem Celery no MVP** — jobs síncronos, polling a cada 3s
- **Soft delete universal** — `is_archived` nunca hard delete
- **Static files** servidos pelo FastAPI em `/static/uploads`
- **CORS** inclui PATCH (necessário para archive/unarchive)

---

## Comandos Úteis

```bash
# Subir ambiente
docker compose up -d

# Rodar testes
docker compose exec api python -m pytest tests/ -v

# Rodar migration
docker compose exec api python -m app.migrations.migrate_sprint_NN

# Ver logs da API
docker compose logs api --tail=30

# Acessar banco diretamente
docker compose exec db psql -U confexai -d confexai_db
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
