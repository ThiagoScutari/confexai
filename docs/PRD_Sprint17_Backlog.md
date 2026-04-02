# PRD — Sprint 17: Backlog Consolidado (5 Sub-Sprints)

**Status:** Aprovação Pendente  
**Data:** 2026-04-02  
**Estrutura:** 5 etapas independentes — cada uma tem seu próprio ciclo inspect → implement → test → audit → commit

---

## Visão Geral das Etapas

| Etapa | Item | Tipo | Esforço | Testes esperados |
|---|---|---|---|---|
| 17.1 | Fix `cleanup_broken_jobs` | fix | Pequeno | 84 → 86 |
| 17.2 | Atualizar 5 skills | docs | Médio | 86 → 86 (sem novos testes) |
| 17.3 | Página de produto unificada | feat | Grande | 86 → 91 |
| 17.4 | Paginação no histórico | feat | Médio | 91 → 95 |
| 17.5 | Estados vazios com orientação | ui | Médio | 95 → 95 (sem novos testes) |

---

## Sprint 17.1 — Fix cleanup_broken_jobs

### Problema
`cleanup_broken_jobs` (jobs.py:280) não filtra `deleted_at == None`. Pode tentar hard-delete de jobs já soft-deleted, corrompendo o registro de auditoria.

### Fix

```python
# backend/app/api/jobs.py — em cleanup_broken_jobs
# ANTES:
broken_jobs = db.query(GenerationJob).filter(
    GenerationJob.result != None,
).all()

# DEPOIS:
broken_jobs = db.query(GenerationJob).filter(
    GenerationJob.result != None,
    GenerationJob.deleted_at == None,  # ← nunca tocar em soft-deleted
).all()
```

### Testes

```python
# backend/tests/test_cleanup.py

def test_cleanup_nao_afeta_jobs_soft_deleted(client, auth_headers, db):
    """Jobs com deleted_at não devem ser processados pelo cleanup."""
    from datetime import datetime
    from app.models import GenerationJob

    job = GenerationJob(
        type="color_variation",
        status="done",
        result='{"jpg_url": "/app/examples/uploads/naoexiste/color_x.jpg"}',
        deleted_at=datetime.utcnow(),
    )
    db.add(job)
    db.commit()

    response = client.delete("/api/v1/jobs/cleanup-broken", headers=auth_headers)
    assert response.status_code == 200

    still_exists = db.query(GenerationJob).filter(
        GenerationJob.id == job.id
    ).first()
    assert still_exists is not None

    db.delete(job)
    db.commit()


def test_cleanup_sem_token_retorna_401(client):
    response = client.delete("/api/v1/jobs/cleanup-broken")
    assert response.status_code == 401
```

### Commits
```
fix(api): filter deleted_at in cleanup_broken_jobs to protect soft-deleted records [S17-1]
test(sprint17): add 2 tests for cleanup with soft-deleted jobs [S17-1]
```

---

## Sprint 17.2 — Atualizar 5 Skills

### Skills desatualizadas (todas paradas no Sprint 01-02)

| Skill | Última versão | O que falta |
|---|---|---|
| `confexai-architecture-decisions` | Sprint 01 | ADRs 10-15, google-genai, PDCA fix |
| `confexai-api-contracts` | Sprint 01 | Endpoints SEO, history, delete, summary |
| `confexai-image-pipeline` | Sprint 01 | job_short_id, color_hex no result, ordem flush/path |
| `confexai-seo-prompts` | Sprint 01 | Rate limiting, Literal types, updated_at |
| `confexai-testing-standards` | Sprint 01 | Padrões Sprints 02-16, mocks, fixtures PIL |

### Para cada skill, o Claude Code deve:
1. Ler o arquivo atual
2. Ler `docs/decisions/ADRs.md` e `docs/SPEC.md` como fonte de verdade
3. Atualizar com o estado real após Sprint 16
4. Manter a estrutura YAML frontmatter + Markdown

### Commit
```
docs(skills): update all 5 ConfexAI skills to reflect Sprints 01-16 state [S17-2]
```

---

## Sprint 17.3 — Página de Produto Unificada

### Endpoint: `GET /products/{id}/summary`

```python
# backend/app/api/products.py
from sqlalchemy import func

@router.get("/{product_id}/summary")
def get_product_summary(
    product_id: UUID,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    product = db.query(Product).filter(
        Product.id == product_id,
        Product.is_active == True,
    ).first()
    if not product:
        raise HTTPException(404, detail="Produto não encontrado.")

    images = db.query(ProductImage).filter(
        ProductImage.product_id == product_id,
        ProductImage.type == "original",
    ).all()

    image_ids = [img.id for img in images]

    approved_jobs = db.query(GenerationJob).filter(
        GenerationJob.product_image_id.in_(image_ids),
        GenerationJob.type == "color_variation",
        GenerationJob.status == "approved",
        GenerationJob.deleted_at == None,
        GenerationJob.is_archived == False,
    ).all() if image_ids else []

    seo = db.query(SEODescription).filter(
        SEODescription.product_id == product_id,
    ).all()

    total_jobs = db.query(GenerationJob).filter(
        GenerationJob.product_image_id.in_(image_ids),
        GenerationJob.deleted_at == None,
    ).count() if image_ids else 0

    total_cost = db.query(
        func.sum(GenerationJob.cost_cents)
    ).filter(
        GenerationJob.product_image_id.in_(image_ids),
        GenerationJob.deleted_at == None,
    ).scalar() or 0 if image_ids else 0

    images_data = [{
        "id": str(img.id),
        "view": img.view,
        "original_url": img.original_url,
        "public_url": path_to_url(img.original_url) if img.original_url else None,
    } for img in images]

    approved_data = []
    for job in approved_jobs:
        result = json.loads(job.result) if job.result else {}
        approved_data.append({
            "id": str(job.id),
            "view": job.product_image.view if job.product_image else None,
            "color_hex": result.get("color_hex"),
            "jpg_url": result.get("jpg_url"),
            "public_url": path_to_url(result["jpg_url"]) if result.get("jpg_url") else None,
        })

    seo_data = [{
        "platform": s.platform,
        "title": s.title,
        "description": s.description,
        "tags": json.loads(s.tags) if s.tags else [],
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    } for s in seo]

    return StandardResponse(data={
        "product": {
            "id": str(product.id),
            "name": product.name,
            "category": product.category,
            "fabric": product.fabric,
            "notes": product.notes,
            "created_at": product.created_at.isoformat(),
        },
        "images": images_data,
        "approved_variations": approved_data,
        "seo": seo_data,
        "stats": {
            "total_jobs": total_jobs,
            "total_cost_cents": total_cost,
            "total_cost_brl": round(total_cost * 0.006, 2),
            "views_uploaded": len(images),
            "variations_approved": len(approved_jobs),
            "platforms_with_seo": len(seo),
        },
    })
```

### Frontend: `frontend/src/pages/Produto.jsx`

Página com 4 abas:
- **Visão Geral** — 4 slots de view (vazio se não enviada) + info do produto
- **Variações** — grid das variações aprovadas (cor, view, thumbnail)
- **SEO** — cards por plataforma com título, tags e botão de cópia
- **Histórico** — custo total + link para `/historico` filtrado

Stats bar no topo: views enviadas, variações aprovadas, plataformas SEO, custo total.

### api.js
```javascript
export const getProductSummary = (productId) =>
  api.get(`/products/${productId}/summary`);
```

### App.jsx
```jsx
import Produto from "./pages/Produto";
// ...
<Route path="produto/:productId" element={<Produto />} />
```

### Produtos.jsx — botão "Ver produto"
```jsx
<button
  onClick={(e) => { e.stopPropagation(); navigate(`/produto/${p.id}`); }}
  className="px-3 py-1.5 text-xs bg-surface-700 hover:bg-surface-600
             border border-surface-600 text-neutral-300 rounded-md transition-colors"
>
  Ver produto
</button>
```

### Testes

```python
# backend/tests/test_product_summary.py

def test_summary_sem_token_retorna_401(client, sample_product):
    response = client.get(f"/api/v1/products/{sample_product.id}/summary")
    assert response.status_code == 401

def test_summary_produto_inexistente_retorna_404(client, auth_headers):
    response = client.get(
        "/api/v1/products/00000000-0000-0000-0000-000000000000/summary",
        headers=auth_headers,
    )
    assert response.status_code == 404

def test_summary_retorna_estrutura_completa(client, auth_headers, sample_product):
    response = client.get(
        f"/api/v1/products/{sample_product.id}/summary",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    for key in ["product", "images", "approved_variations", "seo", "stats"]:
        assert key in data
    assert "total_jobs" in data["stats"]
    assert "total_cost_brl" in data["stats"]
    assert "views_uploaded" in data["stats"]
    assert "variations_approved" in data["stats"]
    assert "platforms_with_seo" in data["stats"]

def test_summary_produto_deletado_retorna_404(client, auth_headers, db):
    from app.models import Product
    p = Product(name="TEST_DEL", category="blusa", fabric="viscose", is_active=False)
    db.add(p)
    db.commit()
    response = client.get(f"/api/v1/products/{p.id}/summary", headers=auth_headers)
    assert response.status_code == 404
    db.delete(p)
    db.commit()

def test_summary_nao_inclui_jobs_deletados(client, auth_headers, sample_product, db):
    """Stats não devem contar jobs com deleted_at."""
    from datetime import datetime
    from app.models import GenerationJob, ProductImage

    # Criar job deletado para o produto
    img = db.query(ProductImage).filter(
        ProductImage.product_id == sample_product.id
    ).first()
    if img:
        job = GenerationJob(
            type="color_variation",
            status="approved",
            product_image_id=img.id,
            deleted_at=datetime.utcnow(),
            cost_cents=3,
        )
        db.add(job)
        db.commit()

        response = client.get(
            f"/api/v1/products/{sample_product.id}/summary",
            headers=auth_headers,
        )
        data = response.json()["data"]
        # Job deletado não deve estar nas approved_variations
        job_ids = [v["id"] for v in data["approved_variations"]]
        assert str(job.id) not in job_ids

        db.delete(job)
        db.commit()
```

### Commits
```
feat(api): add GET /products/{id}/summary endpoint [S17-3]
feat(frontend): add Produto page with 4-tab unified product view [S17-3]
feat(frontend): add getProductSummary to api.js and route in App.jsx [S17-3]
feat(frontend): add "Ver produto" button to Produtos list [S17-3]
test(sprint17): add 5 tests for product summary endpoint [S17-3]
```

---

## Sprint 17.4 — Paginação no Histórico

### Problema
`GET /jobs/history` retorna até 200 jobs numa única chamada. Com crescimento de dados, isso degrada performance e UX.

### Backend: cursor-based pagination

```python
# backend/app/api/jobs.py — em get_history
@router.get("/history")
def get_history(
    product_id: str | None = None,
    limit: int = 50,
    offset: int = 0,        # ← novo
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    query = db.query(GenerationJob).filter(
        GenerationJob.deleted_at == None,
    ).order_by(GenerationJob.created_at.desc())

    if product_id:
        query = query.join(ProductImage).filter(
            ProductImage.product_id == product_id
        )

    total = query.count()
    jobs = query.offset(offset).limit(min(limit, 200)).all()

    # ... montar result ...

    return StandardResponse(data={
        "items": result,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": (offset + len(jobs)) < total,
    })
```

### Frontend: Historico.jsx — botão "Carregar mais"

```jsx
const [offset, setOffset] = useState(0);
const [hasMore, setHasMore] = useState(false);
const [total, setTotal] = useState(0);
const LIMIT = 50;

const loadHistory = async (newOffset = 0, append = false) => {
  setLoading(true);
  try {
    const res = await getHistory(null, LIMIT, newOffset);
    const data = res.data.data;
    setJobs(prev => append ? [...prev, ...data.items] : data.items);
    setHasMore(data.has_more);
    setTotal(data.total);
    setOffset(newOffset + LIMIT);
  } catch {
    toast("Erro ao carregar histórico", "error");
  } finally {
    setLoading(false);
  }
};

// No rodapé da lista:
{hasMore && (
  <button
    onClick={() => loadHistory(offset, true)}
    className="w-full py-3 text-sm text-neutral-400 hover:text-neutral-200
               bg-surface-800 border border-surface-700 rounded-xl transition-colors"
  >
    Carregar mais ({total - jobs.length} restantes)
  </button>
)}
```

### api.js
```javascript
export const getHistory = (productId = null, limit = 50, offset = 0) => {
  const params = { limit, offset };
  if (productId) params.product_id = productId;
  return api.get("/jobs/history", { params });
};
```

### Testes

```python
# backend/tests/test_history_pagination.py

def test_history_paginacao_offset(client, auth_headers):
    r1 = client.get("/api/v1/jobs/history?limit=2&offset=0", headers=auth_headers)
    r2 = client.get("/api/v1/jobs/history?limit=2&offset=2", headers=auth_headers)
    assert r1.status_code == 200
    assert r2.status_code == 200
    data1 = r1.json()["data"]
    data2 = r2.json()["data"]
    assert "items" in data1
    assert "total" in data1
    assert "has_more" in data1
    # IDs das duas páginas não se sobrepõem
    ids1 = {j["id"] for j in data1["items"]}
    ids2 = {j["id"] for j in data2["items"]}
    assert ids1.isdisjoint(ids2)

def test_history_has_more_correto(client, auth_headers):
    r = client.get("/api/v1/jobs/history?limit=1&offset=0", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()["data"]
    if data["total"] > 1:
        assert data["has_more"] is True
    else:
        assert data["has_more"] is False

def test_history_limite_maximo_200(client, auth_headers):
    r = client.get("/api/v1/jobs/history?limit=9999", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data["items"]) <= 200
```

### Commits
```
feat(api): add offset pagination to GET /jobs/history [S17-4]
feat(frontend): add load-more pagination to Historico page [S17-4]
test(sprint17): add 3 tests for history pagination [S17-4]
```

---

## Sprint 17.5 — Estados Vazios com Orientação Visual

### Páginas afetadas

Cada estado vazio deve ter: ícone contextual + mensagem + ação primária.

#### Produtos.jsx — sem produtos cadastrados
```jsx
<div className="flex flex-col items-center justify-center py-24 text-center">
  <div className="w-16 h-16 rounded-2xl bg-surface-800 border border-surface-700
                  flex items-center justify-center mb-4">
    <Package size={28} className="text-neutral-600" />
  </div>
  <h3 className="font-display text-lg text-neutral-300 mb-2">
    Nenhum produto ainda
  </h3>
  <p className="text-sm text-neutral-500 max-w-xs mb-6">
    Crie seu primeiro produto para começar a gerar variações de cor e descrições SEO.
  </p>
  <button onClick={() => setShowCreate(true)}
    className="px-4 py-2 bg-amber-500 hover:bg-amber-400 text-surface-950
               text-sm font-medium rounded-lg transition-colors">
    Criar primeiro produto
  </button>
</div>
```

#### Resultados.jsx — sem variações geradas
```jsx
<div className="flex flex-col items-center justify-center py-24 text-center">
  <div className="w-16 h-16 rounded-2xl bg-surface-800 border border-surface-700
                  flex items-center justify-center mb-4">
    <Images size={28} className="text-neutral-600" />
  </div>
  <h3 className="font-display text-lg text-neutral-300 mb-2">
    Nenhuma variação gerada
  </h3>
  <p className="text-sm text-neutral-500 max-w-xs mb-6">
    Execute um pipeline para gerar variações de cor das suas peças.
  </p>
  <button onClick={() => navigate("/produtos")}
    className="px-4 py-2 bg-amber-500 hover:bg-amber-400 text-surface-950
               text-sm font-medium rounded-lg transition-colors">
    Ir para Produtos
  </button>
</div>
```

#### Historico.jsx — sem execuções
```jsx
<div className="flex flex-col items-center justify-center py-24 text-center">
  <div className="w-16 h-16 rounded-2xl bg-surface-800 border border-surface-700
                  flex items-center justify-center mb-4">
    <Clock size={28} className="text-neutral-600" />
  </div>
  <h3 className="font-display text-lg text-neutral-300 mb-2">
    Histórico vazio
  </h3>
  <p className="text-sm text-neutral-500 max-w-xs">
    As execuções de pipeline aparecerão aqui com prompt, métricas e custo.
  </p>
</div>
```

#### SEO.jsx — sem descrições geradas
```jsx
<div className="flex flex-col items-center justify-center py-20 text-center">
  <div className="w-16 h-16 rounded-2xl bg-surface-800 border border-surface-700
                  flex items-center justify-center mb-4">
    <Sparkles size={28} className="text-neutral-600" />
  </div>
  <h3 className="font-display text-lg text-neutral-300 mb-2">
    Nenhuma descrição gerada
  </h3>
  <p className="text-sm text-neutral-500 max-w-xs mb-6">
    Selecione as plataformas e clique em Gerar SEO para criar títulos e
    descrições otimizados para cada marketplace.
  </p>
</div>
```

### Commit
```
feat(frontend): add contextual empty states with icon, message and CTA to all pages [S17-5]
```

---

## Ordem de Execução (uma etapa por vez, aprovação entre elas)

```
17.1 → inspect → implement → test → audit → commit → APROVAÇÃO
  ↓
17.2 → inspect → implement → audit → commit → APROVAÇÃO
  ↓
17.3 → inspect → implement → test → audit → commit → APROVAÇÃO
  ↓
17.4 → inspect → implement → test → audit → commit → APROVAÇÃO
  ↓
17.5 → inspect → implement → audit → commit → APROVAÇÃO FINAL
```

## Critérios de Aceite por Etapa

### 17.1
- [ ] `cleanup_broken_jobs` filtra `deleted_at == None`
- [ ] 86 passed, 0 failed

### 17.2
- [ ] 5 skills refletem estado real após Sprint 16
- [ ] ADRs 10-15 presentes em `confexai-architecture-decisions`
- [ ] `confexai-image-pipeline` documenta `job_short_id` e ordem `flush → path`

### 17.3
- [ ] `GET /products/{id}/summary` retorna produto + imagens + variações + SEO + stats
- [ ] Página `/produto/:id` com 4 abas funcionais
- [ ] Stats bar com custo total em R$
- [ ] Variações aprovadas no grid com thumbnail
- [ ] 91 passed, 0 failed

### 17.4
- [ ] `GET /jobs/history` aceita `offset` e retorna `has_more`
- [ ] Botão "Carregar mais" aparece quando `has_more=True`
- [ ] 95 passed, 0 failed

### 17.5
- [ ] Estado vazio em: Produtos, Resultados, Histórico, SEO
- [ ] Cada estado tem ícone + mensagem + ação primária
- [ ] Build sem erros
