# PRD — Sprint 09: Limpeza de Dívida Técnica

**Status:** Aprovação Pendente
**Origem:** Itens identificados pela skill de revisão nos Sprints 07 e 08
**Data:** 2026-03-26
**Objetivo:** Resolver dívida técnica acumulada — índices de banco, N+1 queries, scripts de rollback, arquivos não commitados e atualização do CLAUDE.md.

---

## Sumário Executivo

| ID | Tipo | Descrição | Severidade |
|---|---|---|---|
| S09-01 | devops | Commitar arquivos pendentes de sprints anteriores | 🔴 |
| S09-02 | perf | Adicionar índice em `job_api_logs.job_id` | 🟡 |
| S09-03 | perf | Resolver N+1 query em `GET /jobs/history` | 🟡 |
| S09-04 | devops | Criar rollbacks para sprints 07 e 08 | 🟡 |
| S09-05 | docs | Atualizar `CLAUDE.md` com estado atual do projeto | 🟢 |
| S09-06 | devops | Atualizar `.env.example` com todas as variáveis atuais | 🟢 |
| S09-07 | test | Cobrir endpoints sem teste: archive, unarchive, export ZIP | 🟡 |

---

## S09-01 — Commitar Arquivos Pendentes

### Arquivos identificados como uncommitted

```bash
# Verificar antes de commitar:
git status --short
```

Esperado: migrations de sprint 07, url_helper, docs PRDs, CLAUDE.md.
Cada grupo em um commit atômico separado.

---

## S09-02 — Índice em `job_api_logs.job_id`

### `backend/app/migrations/migrate_sprint_09.py`

```python
"""
Migration Sprint 09 — Índices de performance + limpeza de dívida técnica.
Idempotente.
"""
import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://confexai:confexai@localhost/confexai_db")
engine = create_engine(DATABASE_URL)


def index_exists(conn, index_name: str) -> bool:
    result = conn.execute(text(
        f"SELECT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = '{index_name}')"
    ))
    return result.scalar()


def migrate():
    with engine.begin() as conn:
        # Índice em job_api_logs.job_id — queries por job degradam sem isso
        if not index_exists(conn, "ix_job_api_logs_job_id"):
            conn.execute(text(
                "CREATE INDEX ix_job_api_logs_job_id ON job_api_logs(job_id)"
            ))
            print("✅ Índice ix_job_api_logs_job_id criado.")
        else:
            print("✅ Índice ix_job_api_logs_job_id já existe.")

        # Índice em generation_jobs.created_at — GET /history usa ORDER BY created_at DESC
        if not index_exists(conn, "ix_generation_jobs_created_at"):
            conn.execute(text(
                "CREATE INDEX ix_generation_jobs_created_at ON generation_jobs(created_at DESC)"
            ))
            print("✅ Índice ix_generation_jobs_created_at criado.")
        else:
            print("✅ Índice ix_generation_jobs_created_at já existe.")

        # Índice em generation_jobs.is_archived — filtro mais usado
        if not index_exists(conn, "ix_generation_jobs_is_archived"):
            conn.execute(text(
                "CREATE INDEX ix_generation_jobs_is_archived ON generation_jobs(is_archived)"
            ))
            print("✅ Índice ix_generation_jobs_is_archived criado.")
        else:
            print("✅ Índice ix_generation_jobs_is_archived já existe.")

        # Índice em product_images.product_id — JOINs frequentes
        if not index_exists(conn, "ix_product_images_product_id"):
            conn.execute(text(
                "CREATE INDEX ix_product_images_product_id ON product_images(product_id)"
            ))
            print("✅ Índice ix_product_images_product_id criado.")
        else:
            print("✅ Índice ix_product_images_product_id já existe.")


if __name__ == "__main__":
    migrate()
```

### `backend/app/migrations/rollback_sprint_09.py`

```python
"""Rollback Sprint 09 — Remove índices criados."""
import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://confexai:confexai@localhost/confexai_db")
engine = create_engine(DATABASE_URL)


def rollback():
    with engine.begin() as conn:
        for idx in [
            "ix_job_api_logs_job_id",
            "ix_generation_jobs_created_at",
            "ix_generation_jobs_is_archived",
            "ix_product_images_product_id",
        ]:
            conn.execute(text(f"DROP INDEX IF EXISTS {idx}"))
            print(f"✅ Índice {idx} removido.")


if __name__ == "__main__":
    rollback()
```

---

## S09-03 — Resolver N+1 Query em `GET /jobs/history`

### Problema atual

O endpoint faz uma query para cada job para buscar o nome do produto:

```python
# PROBLEMA: N+1 — 100 jobs = 100 queries extras
for j in jobs:
    prod = db.query(Product).filter(Product.id == pid).first()  # ← query por job
```

### Solução: prefetch com dict

```python
@router.get("/history")
def get_history(
    product_id: str | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    from app.models import Product, ProductImage

    query = db.query(GenerationJob).order_by(GenerationJob.created_at.desc())

    if product_id:
        query = query.join(ProductImage).filter(
            ProductImage.product_id == product_id
        )

    jobs = query.limit(limit).all()

    # Prefetch todos os produtos em UMA query
    product_ids = set()
    for j in jobs:
        if j.product_image:
            product_ids.add(j.product_image.product_id)

    products_map = {}
    if product_ids:
        prods = db.query(Product).filter(Product.id.in_(product_ids)).all()
        products_map = {str(p.id): p.name for p in prods}

    # Montar response sem queries adicionais
    result = []
    for j in jobs:
        pid = str(j.product_image.product_id) if j.product_image else None
        product_name = products_map.get(pid) if pid else None
        job_result = json.loads(j.result) if j.result else {}

        result.append({
            "id": str(j.id),
            "product_id": pid,
            "product_name": product_name,
            "view": j.product_image.view if j.product_image else None,
            "type": j.type.value,
            "status": j.status.value,
            "is_archived": j.is_archived,
            "api_used": j.api_used,
            "model_used": j.model_used,
            "prompt_used": j.prompt_used,
            "input_image_url": j.input_image_url,
            "output_jpg_url": job_result.get("jpg_url"),
            "output_png_url": job_result.get("png_url"),
            "color_hex": job_result.get("color_hex"),
            "cost_cents": j.cost_cents,
            "cost_brl": round((j.cost_cents or 0) * 0.006, 4),
            "tokens_used": j.tokens_used,
            "duration_ms": j.duration_ms,
            "error_message": j.error_message,
            "fallback_reason": j.fallback_reason,
            "method": job_result.get("method"),
            "created_at": j.created_at.isoformat(),
            "completed_at": j.completed_at.isoformat() if j.completed_at else None,
        })

    return StandardResponse(data=result)
```

**Resultado:** 100 jobs = 2 queries (1 para jobs, 1 para produtos) em vez de 101.

---

## S09-04 — Rollbacks para Sprints 07 e 08

### `backend/app/migrations/rollback_sprint_07.py`

```python
"""Rollback Sprint 07 — Remove campo is_archived de generation_jobs."""
import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://confexai:confexai@localhost/confexai_db")
engine = create_engine(DATABASE_URL)


def rollback():
    with engine.begin() as conn:
        result = conn.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name='generation_jobs' AND column_name='is_archived'
        """))
        if result.fetchone():
            conn.execute(text("ALTER TABLE generation_jobs DROP COLUMN is_archived"))
            print("✅ Coluna 'is_archived' removida de generation_jobs.")
        else:
            print("✅ Coluna 'is_archived' não existe — nada a fazer.")


if __name__ == "__main__":
    rollback()
```

### `backend/app/migrations/rollback_sprint_08.py`

```python
"""Rollback Sprint 08 — Remove campos de rastreabilidade e tabela job_api_logs."""
import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://confexai:confexai@localhost/confexai_db")
engine = create_engine(DATABASE_URL)

COLUMNS_TO_DROP = [
    "prompt_used", "model_used", "duration_ms",
    "input_image_url", "fallback_reason"
]


def rollback():
    with engine.begin() as conn:
        # Remover tabela job_api_logs
        conn.execute(text("DROP TABLE IF EXISTS job_api_logs CASCADE"))
        print("✅ Tabela 'job_api_logs' removida.")

        # Remover colunas de generation_jobs
        for col in COLUMNS_TO_DROP:
            result = conn.execute(text(f"""
                SELECT column_name FROM information_schema.columns
                WHERE table_name='generation_jobs' AND column_name='{col}'
            """))
            if result.fetchone():
                conn.execute(text(f"ALTER TABLE generation_jobs DROP COLUMN {col}"))
                print(f"✅ Coluna '{col}' removida de generation_jobs.")
            else:
                print(f"✅ Coluna '{col}' não existe — nada a fazer.")


if __name__ == "__main__":
    rollback()
```

---

## S09-05 — Atualizar CLAUDE.md

O `CLAUDE.md` deve refletir o estado atual do projeto após 8 sprints.

### Conteúdo completo do `CLAUDE.md`

```markdown
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
docker compose exec api python -m pytest backend/tests/ -v

# Rodar migration
docker compose exec api python backend/app/migrations/migrate_sprint_NN.py

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
| 09 | Dívida técnica: índices, N+1, rollbacks, docs | — |
```

---

## S09-06 — Atualizar `.env.example`

```env
# Banco
DATABASE_URL=postgresql://confexai:confexai@db:5432/confexai_db
DATABASE_TEST_URL=postgresql://confexai:confexai@db:5432/confexai_test_db

# Segurança
SECRET_KEY=troque-por-uma-chave-segura-de-32-chars

# APIs de IA
ANTHROPIC_API_KEY=
GOOGLE_API_KEY=
KLING_ACCESS_KEY=
KLING_SECRET_KEY=

# Admin (credenciais do usuário padrão no MVP)
ADMIN_EMAIL=admin@confexai.local
ADMIN_PASSWORD_HASH=

# Upload
UPLOAD_DIR=/app/examples/uploads
MAX_IMAGE_SIZE_MB=20
DEFAULT_OUTPUT_FORMAT=jpg
DEFAULT_OUTPUT_RESOLUTION=1200
```

---

## S09-07 — Testes para Endpoints sem Cobertura

### `backend/tests/test_archive.py`

```python
import pytest


def test_archive_job_retorna_200(client, auth_headers, sample_job_pending_review):
    response = client.patch(
        f"/api/v1/jobs/{sample_job_pending_review.id}/archive",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["data"]["is_archived"] is True


def test_unarchive_job_retorna_200(client, auth_headers, sample_job_pending_review):
    # Arquivar primeiro
    client.patch(
        f"/api/v1/jobs/{sample_job_pending_review.id}/archive",
        headers=auth_headers,
    )
    # Depois desarquivar
    response = client.patch(
        f"/api/v1/jobs/{sample_job_pending_review.id}/unarchive",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["data"]["is_archived"] is False


def test_archive_sem_token_retorna_401(client, sample_job_pending_review):
    response = client.patch(f"/api/v1/jobs/{sample_job_pending_review.id}/archive")
    assert response.status_code == 401


def test_archive_job_inexistente_retorna_404(client, auth_headers):
    response = client.patch(
        "/api/v1/jobs/00000000-0000-0000-0000-000000000000/archive",
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_jobs_arquivados_nao_aparecem_na_lista(client, auth_headers, sample_job_pending_review):
    # Arquivar job
    client.patch(
        f"/api/v1/jobs/{sample_job_pending_review.id}/archive",
        headers=auth_headers,
    )
    # Verificar que não aparece na listagem padrão
    response = client.get("/api/v1/jobs", headers=auth_headers)
    ids = [j["id"] for j in response.json()["data"]]
    assert str(sample_job_pending_review.id) not in ids


def test_jobs_arquivados_aparecem_com_include_archived(client, auth_headers, sample_job_pending_review):
    client.patch(
        f"/api/v1/jobs/{sample_job_pending_review.id}/archive",
        headers=auth_headers,
    )
    response = client.get(
        "/api/v1/jobs?include_archived=true",
        headers=auth_headers,
    )
    ids = [j["id"] for j in response.json()["data"]]
    assert str(sample_job_pending_review.id) in ids
```

---

## Ordem de Execução

```
S09-01 (commitar pendentes)
  ↓
S09-02 + S09-04 (migration índices + rollbacks)
  ↓
S09-03 (fix N+1 no /history)
  ↓
Rodar migration + testes
  ↓
S09-05 (CLAUDE.md)
  ↓
S09-06 (.env.example)
  ↓
S09-07 (testes archive/unarchive)
  ↓
Testes finais + commits
```

---

## Commits Atômicos

```
devops(docs): commit pending files from sprints 06-08 [S09-01]
feat(db): add performance indexes for job_api_logs and generation_jobs [S09-02]
feat(db): add rollback scripts for sprints 07, 08, and 09 [S09-04]
perf(api): fix N+1 query in GET /jobs/history with product prefetch [S09-03]
docs(project): update CLAUDE.md with full project state after sprint 08 [S09-05]
devops(config): update .env.example with all current environment variables [S09-06]
test(sprint09): add 6 tests for archive/unarchive endpoints [S09-07]
```

---

## Critérios de Aceite

- [ ] `git status` limpo após S09-01
- [ ] Migration S09 roda sem erros — 4 índices criados
- [ ] Rollbacks de sprints 07, 08 e 09 existem e são idempotentes
- [ ] `GET /jobs/history` com 100 jobs executa em ≤ 2 queries (verificar com logs do SQLAlchemy)
- [ ] `CLAUDE.md` reflete estado real do projeto após Sprint 08
- [ ] `.env.example` tem todas as variáveis necessárias documentadas
- [ ] `pytest` passa com ≥ 50 testes, 0 falhas
- [ ] Nenhuma regressão nos testes existentes
