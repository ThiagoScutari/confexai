# PRD — Sprint 07: Página de Resultados Dedicada com Download e Arquivamento

**Status:** Aprovação Pendente
**Origem:** Demanda crítica — resultados precisam de acesso permanente, organizado e com download
**Data:** 2026-03-26
**Prioridade:** MÁXIMA — bloqueia uso real do sistema

---

## Requisitos Definitivos

1. **Aba "Resultados" fixa na sidebar** — sempre visível, acesso direto sem passar pelo pipeline
2. **Agrupado por produto** — cada produto é um grupo expansível com suas variações
3. **Arquivamento** — soft delete visual (sai da tela principal, fica no banco)
4. **Download obrigatório** em 3 modos:
   - Por imagem individual
   - Por produto (ZIP com todas as imagens aprovadas)
   - Multi-seleção de produtos (ZIP com múltiplos produtos)
5. **Todo resultado é soft delete** — `is_archived` no banco, nunca deletado fisicamente

---

## Sumário Executivo

| ID | Tipo | Descrição | Esforço |
|---|---|---|---|
| S07-01 | feat | Migration: campo `is_archived` em `generation_jobs` | Pequeno |
| S07-02 | feat | Backend: endpoint `PATCH /jobs/{id}/archive` e `unarchive` | Pequeno |
| S07-03 | feat | Backend: endpoint `GET /jobs/export/{product_id}` — ZIP por produto | Médio |
| S07-04 | feat | Backend: endpoint `POST /jobs/export/bulk` — ZIP multi-produto | Médio |
| S07-05 | feat | Frontend: sidebar com item "Resultados" fixo | Pequeno |
| S07-06 | feat | Frontend: página Resultados agrupada por produto com archive | Médio |
| S07-07 | feat | Frontend: download por imagem, por produto e multi-seleção | Médio |

---

## S07-01 — Migration: `is_archived` em `generation_jobs`

### `backend/app/migrations/migrate_sprint_07.py`

```python
"""
Migration Sprint 07 — Adiciona campo is_archived em generation_jobs.
Idempotente.
"""
import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://confexai:confexai@localhost/confexai_db")
engine = create_engine(DATABASE_URL)


def migrate():
    with engine.begin() as conn:
        result = conn.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name='generation_jobs' AND column_name='is_archived'
        """))
        if not result.fetchone():
            conn.execute(text(
                "ALTER TABLE generation_jobs ADD COLUMN is_archived BOOLEAN NOT NULL DEFAULT FALSE"
            ))
            print("✅ Campo 'is_archived' adicionado em generation_jobs.")
        else:
            print("✅ Campo 'is_archived' já existe.")


if __name__ == "__main__":
    migrate()
```

### Alterar `backend/app/models.py` — adicionar campo

```python
class GenerationJob(Base):
    # ... campos existentes ...
    is_archived = Column(Boolean, default=False, nullable=False)  # ← novo
```

---

## S07-02 — Endpoints de Archive/Unarchive

### Adicionar em `backend/app/api/jobs.py`

```python
@router.patch("/{job_id}/archive")
def archive_job(
    job_id: UUID,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    job = db.query(GenerationJob).filter(GenerationJob.id == job_id).first()
    if not job:
        raise HTTPException(404, detail="Job não encontrado.")
    job.is_archived = True
    db.commit()
    return StandardResponse(data={"job_id": str(job_id), "is_archived": True})


@router.patch("/{job_id}/unarchive")
def unarchive_job(
    job_id: UUID,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    job = db.query(GenerationJob).filter(GenerationJob.id == job_id).first()
    if not job:
        raise HTTPException(404, detail="Job não encontrado.")
    job.is_archived = False
    db.commit()
    return StandardResponse(data={"job_id": str(job_id), "is_archived": False})
```

### Alterar `GET /jobs` — filtrar arquivados por padrão

```python
@router.get("")
def list_jobs(
    product_id: str | None = None,
    type: str | None = None,
    status: str | None = None,
    include_archived: bool = False,   # ← novo parâmetro
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    query = db.query(GenerationJob)

    if not include_archived:
        query = query.filter(GenerationJob.is_archived == False)

    # ... restante do filtro igual ...
```

---

## S07-03 — Export ZIP por Produto

### Instalar dependência

`zipfile` é built-in do Python — sem dependência nova.

### Adicionar em `backend/app/api/jobs.py`

```python
import zipfile
import io
from pathlib import Path
from fastapi.responses import StreamingResponse

@router.get("/export/{product_id}")
def export_product_zip(
    product_id: UUID,
    status: str = "approved",   # por padrão exporta só aprovados
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """
    Gera ZIP com todas as imagens geradas para um produto.
    Por padrão exporta apenas jobs aprovados.
    """
    jobs = (
        db.query(GenerationJob)
        .join(ProductImage)
        .filter(
            ProductImage.product_id == product_id,
            GenerationJob.type == JobType.color_variation,
            GenerationJob.is_archived == False,
        )
        .all()
    )

    if status != "all":
        jobs = [j for j in jobs if j.status.value == status]

    if not jobs:
        raise HTTPException(404, detail="Nenhuma imagem encontrada para exportar.")

    # Buscar nome do produto
    from app.models import Product
    product = db.query(Product).filter(Product.id == product_id).first()
    product_name = product.name.replace(" ", "_") if product else str(product_id)

    # Gerar ZIP em memória
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for job in jobs:
            if not job.result:
                continue
            result = json.loads(job.result)
            jpg_url = result.get("jpg_url", "")

            # Converter URL para path no container
            # /static/uploads/uuid/color_696980_frente.jpg
            # → /app/examples/uploads/uuid/color_696980_frente.jpg
            upload_dir = os.getenv("UPLOAD_DIR", "/app/examples/uploads")
            file_path = jpg_url.replace("/static/uploads", upload_dir)

            if not Path(file_path).exists():
                continue

            # Nome do arquivo no ZIP: cor_view.jpg
            color = result.get("color_hex", "").replace("#", "")
            view = job.product_image.view or "sem_view"
            filename = f"{color}_{view}.jpg"

            zf.write(file_path, filename)

    zip_buffer.seek(0)

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename={product_name}_export.zip"
        }
    )
```

---

## S07-04 — Export ZIP Multi-produto

```python
class BulkExportRequest(BaseModel):
    product_ids: list[str]
    status: str = "approved"


@router.post("/export/bulk")
def export_bulk_zip(
    payload: BulkExportRequest,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """
    Gera ZIP com imagens de múltiplos produtos.
    Estrutura: produto_nome/cor_view.jpg
    """
    from app.models import Product

    zip_buffer = io.BytesIO()
    total_files = 0

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for product_id in payload.product_ids:
            product = db.query(Product).filter(Product.id == product_id).first()
            if not product:
                continue

            folder = product.name.replace(" ", "_")[:30]

            jobs = (
                db.query(GenerationJob)
                .join(ProductImage)
                .filter(
                    ProductImage.product_id == product_id,
                    GenerationJob.type == JobType.color_variation,
                    GenerationJob.is_archived == False,
                )
                .all()
            )

            if payload.status != "all":
                jobs = [j for j in jobs if j.status.value == payload.status]

            upload_dir = os.getenv("UPLOAD_DIR", "/app/examples/uploads")

            for job in jobs:
                if not job.result:
                    continue
                result = json.loads(job.result)
                jpg_url = result.get("jpg_url", "")
                file_path = jpg_url.replace("/static/uploads", upload_dir)

                if not Path(file_path).exists():
                    continue

                color = result.get("color_hex", "").replace("#", "")
                view = job.product_image.view or "sem_view"
                filename = f"{folder}/{color}_{view}.jpg"
                zf.write(file_path, filename)
                total_files += 1

    if total_files == 0:
        raise HTTPException(404, detail="Nenhuma imagem encontrada para exportar.")

    zip_buffer.seek(0)

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": "attachment; filename=confexai_export.zip"
        }
    )
```

---

## S07-05 — Sidebar com "Resultados" Fixo

### Alterar `frontend/src/components/Layout.jsx`

```jsx
import { Package, Zap, Images } from "lucide-react";

const navItems = [
  { to: "/produtos", icon: Package, label: "Produtos" },
  { to: "/resultados", icon: Images, label: "Resultados" },
  { to: "/pipeline", icon: Zap, label: "Novo Pipeline" },
];
```

> **Nota:** `/resultados` sem `productId` mostra todos os produtos com resultados.

---

## S07-06 — Página Resultados Agrupada por Produto

### `frontend/src/pages/Resultados.jsx` — reescrever completo

```jsx
import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  ChevronDown, ChevronRight, Download, Archive,
  Check, X, RefreshCw, Package, Images
} from "lucide-react";
import { listJobs, approveJob, rejectJob } from "../services/api";
import { useToast } from "../components/Toast";

const API_BASE = import.meta.env.VITE_API_URL?.replace("/api/v1", "") || "http://localhost:8002";

const VIEW_LABELS = {
  frente: "Frente", costas: "Costas",
  lat_direita: "Lat. D", lat_esquerda: "Lat. E"
};

export default function Resultados() {
  const navigate = useNavigate();
  const { toast } = useToast();

  const [jobsByProduct, setJobsByProduct] = useState({});  // { productId: { product, jobs } }
  const [expanded, setExpanded] = useState({});            // { productId: bool }
  const [selected, setSelected] = useState(new Set());     // Set of productIds for bulk
  const [loading, setLoading] = useState(true);
  const [showArchived, setShowArchived] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const res = await listJobs(null, "color_variation", null, showArchived);
      const jobs = res.data.data;

      // Agrupar por produto
      const grouped = {};
      for (const job of jobs) {
        const pid = job.product_id;
        if (!pid) continue;
        if (!grouped[pid]) {
          grouped[pid] = { productId: pid, productName: job.product_name || pid, jobs: [] };
        }
        grouped[pid].jobs.push(job);
      }
      setJobsByProduct(grouped);

      // Expandir todos por padrão
      const exp = {};
      Object.keys(grouped).forEach((k) => exp[k] = true);
      setExpanded(exp);
    } catch {
      toast("Erro ao carregar resultados", "error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [showArchived]);

  const handleApprove = async (jobId, productId) => {
    try {
      await approveJob(jobId);
      setJobsByProduct((prev) => ({
        ...prev,
        [productId]: {
          ...prev[productId],
          jobs: prev[productId].jobs.map((j) =>
            j.id === jobId ? { ...j, status: "approved" } : j
          ),
        },
      }));
      toast("Aprovado", "success");
    } catch { toast("Erro ao aprovar", "error"); }
  };

  const handleReject = async (jobId, productId) => {
    try {
      await rejectJob(jobId, "Rejeitado pelo operador");
      setJobsByProduct((prev) => ({
        ...prev,
        [productId]: {
          ...prev[productId],
          jobs: prev[productId].jobs.map((j) =>
            j.id === jobId ? { ...j, status: "rejected" } : j
          ),
        },
      }));
      toast("Rejeitado", "info");
    } catch { toast("Erro ao rejeitar", "error"); }
  };

  const handleArchiveProduct = async (productId) => {
    const jobs = jobsByProduct[productId]?.jobs || [];
    try {
      await Promise.all(jobs.map((j) => archiveJob(j.id)));
      toast("Produto arquivado", "info");
      load();
    } catch { toast("Erro ao arquivar", "error"); }
  };

  const downloadProduct = (productId) => {
    const url = `${API_BASE}/api/v1/jobs/export/${productId}`;
    const a = document.createElement("a");
    a.href = url;
    const token = localStorage.getItem("confexai_token");
    // Usar fetch para download autenticado
    fetch(url, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.blob())
      .then((blob) => {
        const blobUrl = URL.createObjectURL(blob);
        a.href = blobUrl;
        a.download = `produto_${productId}.zip`;
        a.click();
        URL.revokeObjectURL(blobUrl);
      })
      .catch(() => toast("Erro ao baixar", "error"));
  };

  const downloadImage = (jpgUrl, filename) => {
    const fullUrl = `${API_BASE}${jpgUrl}`;
    const token = localStorage.getItem("confexai_token");
    fetch(fullUrl, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.blob())
      .then((blob) => {
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = filename || "imagem.jpg";
        a.click();
      })
      .catch(() => toast("Erro ao baixar imagem", "error"));
  };

  const downloadBulk = () => {
    if (selected.size === 0) return;
    const token = localStorage.getItem("confexai_token");
    fetch(`${API_BASE}/api/v1/jobs/export/bulk`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ product_ids: Array.from(selected) }),
    })
      .then((r) => r.blob())
      .then((blob) => {
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = "confexai_export.zip";
        a.click();
      })
      .catch(() => toast("Erro ao baixar seleção", "error"));
  };

  const toggleSelect = (productId) => {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(productId) ? next.delete(productId) : next.add(productId);
      return next;
    });
  };

  const productList = Object.values(jobsByProduct);
  const totalJobs = productList.reduce((sum, p) => sum + p.jobs.length, 0);

  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="font-display text-2xl text-neutral-100">Resultados</h1>
          <p className="text-sm text-neutral-500 mt-1">
            {productList.length} produtos · {totalJobs} variações geradas
          </p>
        </div>
        <div className="flex items-center gap-3">
          {/* Toggle arquivados */}
          <button
            onClick={() => setShowArchived(!showArchived)}
            className={`flex items-center gap-2 px-3 py-2 rounded-md text-xs transition-colors ${
              showArchived
                ? "bg-amber-500/10 text-amber-400 border border-amber-500/30"
                : "bg-surface-700 text-neutral-400 border border-surface-600 hover:text-neutral-200"
            }`}
          >
            <Archive size={14} />
            {showArchived ? "Ocultar arquivados" : "Ver arquivados"}
          </button>

          {/* Download seleção */}
          {selected.size > 0 && (
            <button
              onClick={downloadBulk}
              className="flex items-center gap-2 px-4 py-2 bg-amber-500 hover:bg-amber-400 text-surface-950 rounded-md text-sm font-medium transition-colors"
            >
              <Download size={14} />
              Baixar seleção ({selected.size})
            </button>
          )}

          <button
            onClick={load}
            className="p-2 bg-surface-700 hover:bg-surface-600 text-neutral-400 rounded-md transition-colors"
          >
            <RefreshCw size={14} />
          </button>
        </div>
      </div>

      {loading ? (
        <div className="space-y-3">
          {[1, 2].map((i) => (
            <div key={i} className="bg-surface-800 border border-surface-700 rounded-xl p-5 animate-pulse">
              <div className="h-4 w-48 bg-surface-700 rounded mb-3" />
              <div className="grid grid-cols-4 gap-3">
                {[1,2,3,4].map((j) => (
                  <div key={j} className="aspect-square bg-surface-700 rounded-lg" />
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : productList.length === 0 ? (
        <div className="text-center py-20 text-neutral-600">
          <Images size={40} className="mx-auto mb-3 opacity-30" />
          <p className="text-sm">Nenhum resultado gerado ainda</p>
          <button
            onClick={() => navigate("/produtos")}
            className="mt-4 text-sm text-amber-400 hover:text-amber-300 transition-colors"
          >
            Ir para produtos →
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {productList.map(({ productId, productName, jobs }) => {
            const isExpanded = expanded[productId];
            const isSelected = selected.has(productId);
            const approvedCount = jobs.filter((j) => j.status === "approved").length;
            const pendingCount = jobs.filter((j) => j.status === "pending_review").length;

            return (
              <div
                key={productId}
                className={`bg-surface-800 border rounded-xl transition-all ${
                  isSelected ? "border-amber-500/40" : "border-surface-600"
                }`}
              >
                {/* Product header */}
                <div className="flex items-center gap-3 px-5 py-4">
                  {/* Checkbox seleção */}
                  <button
                    onClick={() => toggleSelect(productId)}
                    className={`w-5 h-5 rounded border flex items-center justify-center shrink-0 transition-all ${
                      isSelected
                        ? "bg-amber-500 border-amber-500"
                        : "border-surface-500 hover:border-amber-500"
                    }`}
                  >
                    {isSelected && <Check size={12} className="text-surface-950" />}
                  </button>

                  {/* Expand toggle */}
                  <button
                    onClick={() => setExpanded((prev) => ({ ...prev, [productId]: !isExpanded }))}
                    className="flex items-center gap-3 flex-1 text-left"
                  >
                    <div className="w-7 h-7 bg-amber-500/10 rounded flex items-center justify-center shrink-0">
                      <Package size={14} className="text-amber-400" />
                    </div>
                    <div>
                      <p className="text-sm font-medium text-neutral-100">{productName}</p>
                      <p className="text-xs text-neutral-500 mt-0.5">
                        {jobs.length} variações ·{" "}
                        <span className="text-emerald-400">{approvedCount} aprovadas</span>
                        {pendingCount > 0 && (
                          <span className="text-amber-400"> · {pendingCount} pendentes</span>
                        )}
                      </p>
                    </div>
                    {isExpanded
                      ? <ChevronDown size={16} className="text-neutral-500 ml-auto" />
                      : <ChevronRight size={16} className="text-neutral-500 ml-auto" />
                    }
                  </button>

                  {/* Actions */}
                  <div className="flex items-center gap-2 shrink-0">
                    <button
                      onClick={() => downloadProduct(productId)}
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-surface-700 hover:bg-surface-600 border border-surface-600 text-neutral-300 rounded-md text-xs transition-colors"
                    >
                      <Download size={12} />
                      Baixar produto
                    </button>
                    <button
                      onClick={() => handleArchiveProduct(productId)}
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-surface-700 hover:bg-surface-600 border border-surface-600 text-neutral-500 hover:text-neutral-300 rounded-md text-xs transition-colors"
                    >
                      <Archive size={12} />
                      Arquivar
                    </button>
                  </div>
                </div>

                {/* Jobs grid */}
                {isExpanded && (
                  <div className="px-5 pb-5">
                    <div className="border-t border-surface-700 pt-4">
                      <div className="grid grid-cols-4 gap-3">
                        {jobs.map((job) => {
                          const result = job.result;
                          const jpgUrl = result?.jpg_url;
                          const fullUrl = jpgUrl ? `${API_BASE}${jpgUrl}` : null;
                          const colorHex = result?.color_hex || "#888";
                          const colorName = colorHex.replace("#", "");
                          const viewLabel = VIEW_LABELS[job.view] || job.view || "";
                          const filename = `${colorName}_${job.view || "img"}.jpg`;

                          return (
                            <div
                              key={job.id}
                              className={`bg-surface-700 border rounded-lg overflow-hidden transition-all ${
                                job.status === "approved" ? "border-emerald-500/30" :
                                job.status === "rejected" ? "border-red-500/20 opacity-40" :
                                "border-surface-600"
                              }`}
                            >
                              {/* Image */}
                              <div className="relative aspect-square bg-surface-800">
                                {fullUrl ? (
                                  <img
                                    src={fullUrl}
                                    alt={filename}
                                    className="w-full h-full object-contain"
                                  />
                                ) : (
                                  <div
                                    className="w-full h-full"
                                    style={{ backgroundColor: colorHex }}
                                  />
                                )}
                                {/* Badges */}
                                <div className="absolute top-1.5 left-1.5 flex gap-1">
                                  {viewLabel && (
                                    <span className="text-xs bg-black/60 text-white px-1.5 py-0.5 rounded font-mono">
                                      {viewLabel}
                                    </span>
                                  )}
                                </div>
                                {/* Download button overlay */}
                                {fullUrl && (
                                  <button
                                    onClick={() => downloadImage(jpgUrl, filename)}
                                    className="absolute top-1.5 right-1.5 w-6 h-6 bg-black/60 hover:bg-black/80 text-white rounded flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                                    title="Baixar imagem"
                                  >
                                    <Download size={11} />
                                  </button>
                                )}
                              </div>

                              {/* Info + actions */}
                              <div className="p-2">
                                <div className="flex items-center justify-between mb-1.5">
                                  <span className="text-xs font-mono text-neutral-400">
                                    {colorHex}
                                  </span>
                                  {fullUrl && (
                                    <button
                                      onClick={() => downloadImage(jpgUrl, filename)}
                                      className="text-neutral-600 hover:text-amber-400 transition-colors"
                                      title="Baixar"
                                    >
                                      <Download size={11} />
                                    </button>
                                  )}
                                </div>

                                {job.status === "pending_review" && (
                                  <div className="flex gap-1">
                                    <button
                                      onClick={() => handleApprove(job.id, productId)}
                                      className="flex-1 flex items-center justify-center gap-1 py-1 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 rounded text-xs transition-colors"
                                    >
                                      <Check size={10} /> Ok
                                    </button>
                                    <button
                                      onClick={() => handleReject(job.id, productId)}
                                      className="flex-1 flex items-center justify-center gap-1 py-1 bg-red-500/10 hover:bg-red-500/20 text-red-400 rounded text-xs transition-colors"
                                    >
                                      <X size={10} /> Não
                                    </button>
                                  </div>
                                )}
                                {job.status === "approved" && (
                                  <p className="text-xs text-emerald-400 text-center py-1">Aprovado</p>
                                )}
                                {job.status === "rejected" && (
                                  <p className="text-xs text-red-400 text-center py-1">Rejeitado</p>
                                )}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
```

---

## S07-07 — Adicionar `product_name` e `include_archived` no GET /jobs

### Alterar `backend/app/api/jobs.py` — GET /jobs

```python
@router.get("")
def list_jobs(
    product_id: str | None = None,
    type: str | None = None,
    status: str | None = None,
    include_archived: bool = False,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    from app.models import Product

    query = db.query(GenerationJob)

    if not include_archived:
        query = query.filter(GenerationJob.is_archived == False)

    if product_id:
        query = query.join(ProductImage).filter(
            ProductImage.product_id == product_id
        )
    if type:
        query = query.filter(GenerationJob.type == type)
    if status:
        query = query.filter(GenerationJob.status == status)

    jobs = query.order_by(GenerationJob.created_at.desc()).limit(200).all()

    result = []
    for j in jobs:
        pid = str(j.product_image.product_id) if j.product_image else None
        product_name = None
        if pid:
            prod = db.query(Product).filter(Product.id == pid).first()
            product_name = prod.name if prod else None

        result.append({
            "id": str(j.id),
            "type": j.type.value,
            "status": j.status.value,
            "api_used": j.api_used,
            "cost_cents": j.cost_cents,
            "is_archived": j.is_archived,
            "result": json.loads(j.result) if j.result else None,
            "created_at": j.created_at.isoformat(),
            "completed_at": j.completed_at.isoformat() if j.completed_at else None,
            "product_id": pid,
            "product_name": product_name,
            "view": j.product_image.view if j.product_image else None,
        })

    return StandardResponse(data=result)
```

### Adicionar `archiveJob` e `listJobs` com `include_archived` em `frontend/src/services/api.js`

```javascript
export const archiveJob = (jobId) =>
  api.patch(`/jobs/${jobId}/archive`);

export const unarchiveJob = (jobId) =>
  api.patch(`/jobs/${jobId}/unarchive`);

// Atualizar listJobs para aceitar include_archived:
export const listJobs = (productId = null, type = null, status = null, includeArchived = false) => {
  const params = {};
  if (productId) params.product_id = productId;
  if (type) params.type = type;
  if (status) params.status = status;
  if (includeArchived) params.include_archived = true;
  return api.get("/jobs", { params });
};
```

---

## Ordem de Execução

```
S07-01 (migration)
  ↓
S07-02 (archive/unarchive endpoints)
  ↓
S07-07 (GET /jobs com product_name + include_archived)
  ↓
S07-03 (export ZIP produto)
  ↓
S07-04 (export ZIP bulk)
  ↓
S07-05 (sidebar)
  ↓
S07-06 (página Resultados completa)
  ↓
services/api.js (archiveJob + listJobs atualizado)
```

---

## Commits Atômicos

```
feat(db): add is_archived field to generation_jobs sprint 07 migration [S07-01]
feat(api): add archive/unarchive endpoints for jobs [S07-02]
feat(api): add product_name and include_archived to GET /jobs [S07-07]
feat(api): add export ZIP per product endpoint [S07-03]
feat(api): add bulk export ZIP multi-product endpoint [S07-04]
feat(frontend): add Resultados to sidebar navigation [S07-05]
feat(frontend): rewrite Resultados page grouped by product with archive and download [S07-06]
feat(frontend): add archiveJob, unarchiveJob and update listJobs in api service [S07-07]
```

---

## Critérios de Aceite

- [ ] "Resultados" aparece na sidebar — sempre visível
- [ ] Página agrupa variações por produto em acordeão expansível
- [ ] Checkbox de seleção por produto para download em lote
- [ ] Botão "Baixar produto" gera ZIP com imagens aprovadas
- [ ] Botão "Baixar seleção" com N produtos gera ZIP organizado por pasta
- [ ] Ícone de download em cada imagem individual funciona
- [ ] Botão "Arquivar" remove produto da view principal (mantém no banco)
- [ ] Toggle "Ver arquivados" mostra produtos arquivados
- [ ] Aprovar/rejeitar funciona direto nos cards
- [ ] Migration roda sem erros
- [ ] Testes passam sem regressões
