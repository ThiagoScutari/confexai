# PRD — Sprint 15: UI/UX Virada 360

**Status:** Aprovação Pendente  
**Origem:** Auditoria visual do frontend após Sprint 14  
**Data:** 2026-03-31  
**Objetivo:** Elevar consistência e qualidade visual do frontend em todas as páginas, com foco em hierarquia, feedback e identidade dos cards de resultado.

---

## Sumário Executivo

| ID | Tipo | Descrição | Esforço |
|---|---|---|---|
| S15-01 | ux | Hierarquia visual de botões — primário, secundário, destrutivo | Pequeno |
| S15-02 | ux | Skeleton loaders substituindo spinners genéricos | Médio |
| S15-03 | ux | Cards de resultado com identidade visual forte + nome e ID do job | Médio |
| S15-04 | feat | Soft delete com `deleted_at` — job some da UI, permanece no banco | Médio |
| S15-05 | ux | Inputs com foco âmbar + validação inline | Pequeno |
| S15-06 | ux | Hierarquia tipográfica e espaçamento consistentes em todas as páginas | Pequeno |

---

## S15-01 — Hierarquia de Botões

### Problema
Botões primários, secundários e destrutivos têm aparência similar. O usuário não consegue identificar a ação principal.

### Padrão obrigatório (aplicar em TODAS as páginas)

```jsx
// PRIMÁRIO — ação principal da página
<button className="px-4 py-2 bg-amber-500 hover:bg-amber-400 text-surface-950 font-medium rounded-lg transition-colors">
  Gerar variações
</button>

// SECUNDÁRIO — ação de suporte
<button className="px-4 py-2 bg-surface-700 hover:bg-surface-600 border border-surface-600 text-neutral-300 rounded-lg transition-colors">
  Ver histórico
</button>

// DESTRUTIVO — delete, rejeitar, excluir
<button className="px-4 py-2 bg-red-950/40 hover:bg-red-900/60 border border-red-800/40 text-red-400 hover:text-red-300 rounded-lg transition-colors">
  Excluir
</button>

// GHOST — ação terciária, contexto denso
<button className="px-3 py-1.5 text-neutral-400 hover:text-neutral-100 hover:bg-surface-700 rounded-md transition-colors text-sm">
  Cancelar
</button>
```

### Páginas a corrigir

- `Produtos.jsx` — botões "Pipeline", "Resultados", "SEO" nos cards: usar secundário padrão
- `Pipeline.jsx` — "Executar pipeline" → primário; "Cancelar" → ghost
- `Resultados.jsx` — "Aprovar" → primário; "Rejeitar" → destrutivo; "Arquivar" → ghost
- `SEO.jsx` — "Gerar SEO" → primário; demais → secundários

---

## S15-02 — Skeleton Loaders

### Problema
Spinners genéricos não comunicam estrutura da página. O usuário não sabe o que está sendo carregado.

### Criar `frontend/src/components/Skeleton.jsx`

```jsx
export function SkeletonCard({ className = "" }) {
  return (
    <div className={`bg-surface-800 border border-surface-700 rounded-xl overflow-hidden animate-pulse ${className}`}>
      <div className="aspect-square bg-surface-700" />
      <div className="p-3 space-y-2">
        <div className="h-3 bg-surface-700 rounded w-16" />
        <div className="h-3 bg-surface-600 rounded w-24" />
      </div>
    </div>
  );
}

export function SkeletonRow({ className = "" }) {
  return (
    <div className={`bg-surface-800 border border-surface-700 rounded-lg h-14 animate-pulse ${className}`} />
  );
}

export function SkeletonProductCard() {
  return (
    <div className="bg-surface-800 border border-surface-700 rounded-xl p-5 animate-pulse">
      <div className="h-4 bg-surface-700 rounded w-2/3 mb-3" />
      <div className="h-3 bg-surface-700 rounded w-1/3 mb-4" />
      <div className="flex gap-2">
        <div className="h-7 bg-surface-700 rounded w-20" />
        <div className="h-7 bg-surface-700 rounded w-20" />
        <div className="h-7 bg-surface-700 rounded w-14" />
      </div>
    </div>
  );
}

export function SkeletonSEOCard() {
  return (
    <div className="bg-surface-800 border border-surface-700 rounded-xl p-5 animate-pulse space-y-3">
      <div className="h-3 bg-surface-700 rounded w-24" />
      <div className="h-4 bg-surface-700 rounded w-full" />
      <div className="h-20 bg-surface-600 rounded w-full" />
      <div className="flex gap-1 flex-wrap">
        {[1,2,3,4].map(i => <div key={i} className="h-5 bg-surface-700 rounded w-16" />)}
      </div>
    </div>
  );
}
```

### Aplicação por página

| Página | Skeleton | Quantidade |
|---|---|---|
| `Produtos.jsx` | `SkeletonProductCard` | 3 |
| `Resultados.jsx` | `SkeletonCard` | 8 em grid |
| `Historico.jsx` | `SkeletonRow` | 5 |
| `SEO.jsx` | `SkeletonSEOCard` | 3 |

### Padrão de uso

```jsx
// ANTES
if (loading) return <div className="flex justify-center"><Spinner /></div>;

// DEPOIS — skeleton contextual
if (loading) return (
  <div className="grid grid-cols-4 gap-3">
    {[1,2,3,4,5,6,7,8].map(i => <SkeletonCard key={i} />)}
  </div>
);
```

---

## S15-03 — Cards de Resultado com Identidade Visual Forte

### Problema
Cards na página de Resultados não comunicam contexto: sem nome da cor, sem ID curto do job visível, status pouco diferenciado.

### Estrutura do novo card

```jsx
<div
  key={job.id}
  className={`relative bg-surface-800 rounded-xl overflow-hidden border-2 transition-all group ${
    isJobSelected
      ? "border-amber-500 ring-2 ring-amber-500/20"
      : job.status === "approved"
        ? "border-emerald-500/40"
        : job.status === "rejected"
          ? "border-red-500/20 opacity-50"
          : "border-surface-600 hover:border-surface-500"
  }`}
>
  {/* Imagem */}
  <div className="relative aspect-square bg-surface-900">
    {fullUrl ? (
      <img src={fullUrl} alt={colorName} className="w-full h-full object-contain" />
    ) : (
      <div className="w-full h-full flex items-center justify-center">
        <div className="w-12 h-12 rounded-full border border-white/10" style={{ backgroundColor: colorHex }} />
      </div>
    )}

    {/* Overlay clicável para seleção */}
    <div
      onClick={() => toggleImage(job.id)}
      className="absolute inset-0 cursor-pointer"
    />

    {/* Checkbox — canto inferior esquerdo */}
    <div
      onClick={(e) => { e.stopPropagation(); toggleImage(job.id); }}
      className={`absolute bottom-2 left-2 w-5 h-5 rounded border-2 flex items-center justify-center cursor-pointer z-10 transition-all ${
        isJobSelected
          ? "bg-amber-500 border-amber-500"
          : "bg-black/50 border-white/30 hover:border-amber-400"
      }`}
    >
      {isJobSelected && <Check size={11} className="text-surface-950" />}
    </div>

    {/* View badge — canto superior esquerdo */}
    {viewLabel && (
      <span className="absolute top-2 left-2 text-xs bg-black/70 text-white px-1.5 py-0.5 rounded font-mono z-10">
        {viewLabel}
      </span>
    )}

    {/* Ações — surgem no hover, canto superior direito */}
    <div className="absolute top-2 right-2 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity z-10">
      {fullUrl && (
        <button
          onClick={(e) => { e.stopPropagation(); downloadImage(jpgUrl, filename); }}
          className="w-6 h-6 bg-black/70 hover:bg-black/90 text-white rounded flex items-center justify-center"
          title="Baixar"
        >
          <Download size={11} />
        </button>
      )}
      {!job.is_archived ? (
        <button
          onClick={(e) => { e.stopPropagation(); handleArchiveJob(job.id, productId); }}
          className="w-6 h-6 bg-black/70 hover:bg-amber-900/80 text-neutral-400 hover:text-amber-300 rounded flex items-center justify-center"
          title="Arquivar"
        >
          <Archive size={11} />
        </button>
      ) : (
        <button
          onClick={(e) => { e.stopPropagation(); handleUnarchiveJob(job.id, productId); }}
          className="w-6 h-6 bg-black/70 hover:bg-emerald-900/80 text-neutral-400 hover:text-emerald-300 rounded flex items-center justify-center"
          title="Desarquivar"
        >
          <ArchiveRestore size={11} />
        </button>
      )}
      <button
        onClick={(e) => { e.stopPropagation(); handleDeleteJob(job.id, productId); }}
        className="w-6 h-6 bg-black/70 hover:bg-red-900/90 text-neutral-400 hover:text-red-400 rounded flex items-center justify-center"
        title="Excluir da visualização"
      >
        <Trash2 size={11} />
      </button>
    </div>

    {/* Status badge — canto inferior direito */}
    {job.status === "approved" && (
      <span className="absolute bottom-2 right-2 flex items-center gap-0.5 text-xs bg-emerald-500/20 text-emerald-400 px-1.5 py-0.5 rounded font-medium z-10">
        <Check size={9} /> OK
      </span>
    )}
    {job.status === "rejected" && (
      <span className="absolute bottom-2 right-2 flex items-center gap-0.5 text-xs bg-red-500/20 text-red-400 px-1.5 py-0.5 rounded font-medium z-10">
        <X size={9} /> Rej
      </span>
    )}
  </div>

  {/* Footer do card */}
  <div className="p-2.5">
    <div className="flex items-center gap-1.5 mb-0.5">
      <div
        className="w-3 h-3 rounded-full border border-white/10 shrink-0"
        style={{ backgroundColor: colorHex }}
      />
      <span className="text-xs font-medium text-neutral-200 truncate">
        {colorName || colorHex}
      </span>
    </div>
    <p className="text-xs font-mono text-neutral-600">
      {String(job.id).slice(0, 8)}
    </p>
  </div>
</div>
```

---

## S15-04 — Soft Delete com `deleted_at`

### Motivação
`is_archived` esconde mas é recuperável via toggle. O usuário quer uma forma de "nunca mais ver esta imagem" sem hard delete — o registro permanece no banco para auditoria, mas some de toda listagem.

### Migration `backend/app/migrations/migrate_sprint_15.py`

```python
"""Migration Sprint 15 — deleted_at em generation_jobs. Idempotente."""
import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://confexai:confexai@localhost/confexai_db")
engine = create_engine(DATABASE_URL)

def column_exists(conn, table, column):
    r = conn.execute(text(
        f"SELECT EXISTS (SELECT 1 FROM information_schema.columns "
        f"WHERE table_name='{table}' AND column_name='{column}')"
    ))
    return r.scalar()

def migrate():
    with engine.begin() as conn:
        if not column_exists(conn, "generation_jobs", "deleted_at"):
            conn.execute(text(
                "ALTER TABLE generation_jobs ADD COLUMN deleted_at TIMESTAMP NULL"
            ))
            print("✅ Coluna 'deleted_at' adicionada em generation_jobs.")
        else:
            print("✅ 'deleted_at' já existe.")

if __name__ == "__main__":
    migrate()
```

### Rollback `backend/app/migrations/rollback_sprint_15.py`

```python
"""Rollback Sprint 15."""
import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://confexai:confexai@localhost/confexai_db")
engine = create_engine(DATABASE_URL)

def rollback():
    with engine.begin() as conn:
        conn.execute(text(
            "ALTER TABLE generation_jobs DROP COLUMN IF EXISTS deleted_at"
        ))
        print("✅ Coluna 'deleted_at' removida.")

if __name__ == "__main__":
    rollback()
```

### Model `backend/app/models.py`

```python
# Adicionar em GenerationJob após fallback_reason:
deleted_at = Column(DateTime, nullable=True, default=None)
```

### Endpoint `backend/app/api/jobs.py`

```python
@router.patch("/{job_id}/delete")
def soft_delete_job(
    job_id: UUID,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """
    Marca job como excluído (deleted_at). Não aparece mais em nenhuma listagem.
    O registro permanece no banco para auditoria.
    """
    job = db.query(GenerationJob).filter(
        GenerationJob.id == job_id,
        GenerationJob.deleted_at == None,
    ).first()
    if not job:
        raise HTTPException(404, detail="Job não encontrado.")

    job.deleted_at = datetime.utcnow()
    db.commit()
    return StandardResponse(data={
        "id": str(job.id),
        "deleted_at": job.deleted_at.isoformat(),
    })
```

### Filtro na listagem — adicionar `deleted_at == None` em:

```python
# list_jobs, get_history, e qualquer outro query de GenerationJob
query = query.filter(
    GenerationJob.deleted_at == None  # ← adicionar em todas as queries de listagem
)
```

### Frontend

```javascript
// frontend/src/services/api.js
export const deleteJob = (jobId) =>
  api.patch(`/jobs/${jobId}/delete`);
```

```jsx
// Resultados.jsx — handler
const handleDeleteJob = async (jobId, productId) => {
  if (!window.confirm("Remover esta imagem da visualização permanentemente?")) return;
  try {
    await deleteJob(jobId);
    setJobsByProduct(prev => {
      const updated = { ...prev };
      if (updated[productId]) {
        updated[productId] = {
          ...updated[productId],
          jobs: updated[productId].jobs.filter(j => j.id !== jobId),
        };
      }
      return updated;
    });
    toast("Imagem removida da visualização", "success");
  } catch (err) {
    toast(err.response?.data?.detail || "Erro ao remover", "error");
  }
};
```

---

## S15-05 — Inputs com Foco Âmbar + Validação Inline

### Adicionar em `frontend/src/index.css`

```css
@layer components {
  .input-base {
    @apply bg-surface-700 border border-surface-600 text-neutral-100
           rounded-lg px-3 py-2 text-sm w-full transition-all outline-none
           placeholder:text-neutral-600
           focus:border-amber-500 focus:ring-2 focus:ring-amber-500/20;
  }

  .input-error {
    @apply border-red-500/60 focus:border-red-400 focus:ring-red-500/20;
  }
}
```

### Substituir todos os inputs em:

- `Produtos.jsx` — campo nome do produto no modal de criação
- `Pipeline.jsx` — campos de cor HEX
- `SEO.jsx` — campos de contexto

### Padrão de validação inline

```jsx
<div className="space-y-1">
  <label className="text-xs text-neutral-500 uppercase tracking-wider">
    Nome do produto
  </label>
  <input
    value={name}
    onChange={e => setName(e.target.value)}
    className={`input-base ${error.name ? "input-error" : ""}`}
    placeholder="Ex: Blusa Floral Viscose"
  />
  {error.name && (
    <p className="text-xs text-red-400 flex items-center gap-1 mt-0.5">
      <AlertCircle size={11} /> {error.name}
    </p>
  )}
</div>
```

---

## S15-06 — Hierarquia Tipográfica e Espaçamento

### Regras aplicar em todas as páginas

```jsx
// H1 de página — sempre font-display
<h1 className="font-display text-2xl text-neutral-100">Nome da Página</h1>

// Subtítulo / contagem
<p className="text-sm text-neutral-500 mt-1">24 variações geradas</p>

// Nome principal em card (peso forte)
<p className="text-sm font-medium text-neutral-100">{product.name}</p>

// Metadado secundário
<p className="text-xs text-neutral-500">{product.category}</p>

// Dado técnico — sempre JetBrains Mono
<span className="text-xs font-mono text-neutral-600">{job.id.slice(0,8)}</span>

// Número de destaque
<span className="text-sm font-medium text-amber-400">{count}</span>
```

### Espaçamentos padrão

```jsx
// Header da página
<div className="mb-8">...</div>

// Entre seções
<div className="space-y-6">...</div>

// Entre cards numa lista
<div className="space-y-2">...</div>

// Grid de imagens
<div className="grid grid-cols-4 gap-3">...</div>
```

---

## Testes — S15-04

### `backend/tests/test_job_delete.py`

```python
def test_delete_job_sem_token_retorna_401(client, sample_job_pending_review):
    response = client.patch(f"/api/v1/jobs/{sample_job_pending_review.id}/delete")
    assert response.status_code == 401

def test_delete_job_retorna_200_com_deleted_at(client, auth_headers, sample_job_pending_review):
    response = client.patch(
        f"/api/v1/jobs/{sample_job_pending_review.id}/delete",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert "deleted_at" in response.json()["data"]

def test_job_deletado_nao_aparece_na_listagem(client, auth_headers, sample_job_pending_review):
    client.patch(
        f"/api/v1/jobs/{sample_job_pending_review.id}/delete",
        headers=auth_headers,
    )
    response = client.get("/api/v1/jobs", headers=auth_headers)
    ids = [j["id"] for j in response.json()["data"]]
    assert str(sample_job_pending_review.id) not in ids

def test_delete_job_inexistente_retorna_404(client, auth_headers):
    response = client.patch(
        "/api/v1/jobs/00000000-0000-0000-0000-000000000000/delete",
        headers=auth_headers,
    )
    assert response.status_code == 404

def test_delete_job_duas_vezes_retorna_404(client, auth_headers, sample_job_pending_review):
    client.patch(
        f"/api/v1/jobs/{sample_job_pending_review.id}/delete",
        headers=auth_headers,
    )
    response = client.patch(
        f"/api/v1/jobs/{sample_job_pending_review.id}/delete",
        headers=auth_headers,
    )
    assert response.status_code == 404
```

---

## Ordem de Execução

```
S15-01 — Hierarquia de botões (todas as páginas)
  ↓
S15-05 — input-base CSS + aplicar nos formulários
  ↓
S15-06 — Hierarquia tipográfica (todas as páginas)
  ↓
S15-02 — Skeleton.jsx + substituir spinners
  ↓
S15-04 — Migration + modelo + endpoint + frontend delete
  ↓
S15-03 — Redesign dos cards de resultado
  ↓
Rodar migration + testes
  ↓
Auditoria sgp-sprint-review (ANTES dos commits)
  ↓
Verificação visual no browser
  ↓
Commits atômicos
```

---

## Commits Atômicos

```
feat(frontend): standardize button hierarchy — primary, secondary, destructive [S15-01]
feat(frontend): add input-base CSS class with amber focus and inline validation [S15-05]
feat(frontend): improve typographic hierarchy and spacing across all pages [S15-06]
feat(frontend): add Skeleton components and replace generic spinners [S15-02]
feat(db): add deleted_at to generation_jobs for permanent soft delete [S15-04]
feat(api): add PATCH /jobs/{id}/delete endpoint [S15-04]
feat(frontend): add delete job button and handler in Resultados [S15-04]
feat(frontend): redesign result cards with color swatch, name, short ID [S15-03]
test(sprint15): add 5 tests for soft delete endpoint [S15-04]
```

---

## Critérios de Aceite

- [ ] Botão primário âmbar vs secundário surface vs destrutivo red — visualmente distintos em todas as páginas
- [ ] Loading states mostram skeletons contextuais — não spinners
- [ ] Cards de resultado mostram: swatch de cor, nome da cor, view badge, ID curto (8 chars), status badge
- [ ] Botão de delete (Trash2) aparece no hover do card — pede confirmação antes de executar
- [ ] Job com `deleted_at` não aparece em `/jobs`, `/jobs/history`, nem em Resultados
- [ ] Inputs têm borda âmbar no foco — vermelho + mensagem em erro
- [ ] Hierarquia tipográfica: h1 display, texto principal neutral-100, metadados neutral-500, técnico mono
- [ ] `pytest tests/ -v` → **73 passed, 0 failed**
- [ ] Auditoria `sgp-sprint-review` aprovada antes dos commits
- [ ] Build do frontend sem erros
- [ ] Verificação visual no browser aprovada pelo arquiteto
