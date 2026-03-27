# PRD — Sprint 06: Refinamento de UX — Loading States, Feedback de Erros e Melhorias Visuais

**Status:** Aprovação Pendente
**Origem:** Refinamento operacional — tornar o sistema prazeroso de usar no dia a dia
**Data:** 2026-03-26
**Objetivo:** Eliminar estados de incerteza (o que está acontecendo?), comunicar erros claramente, e polir detalhes visuais que fazem a interface sentir profissional.

---

## Problemas Identificados

| # | Problema | Impacto |
|---|---|---|
| 1 | Pipeline roda sem feedback de progresso — parece travado | Alto — operador não sabe se está processando |
| 2 | Erros de API aparecem como falha silenciosa ou console | Alto — sem mensagem útil ao usuário |
| 3 | Cards de resultado não mostram a view da peça (frente/costas) | Médio — difícil identificar qual variação é qual |
| 4 | Botão "Executar pipeline" não tem confirmação de custo estimado | Médio — surpresa no custo |
| 5 | Sem indicação visual durante upload individual de imagem | Baixo — upload parece instantâneo |
| 6 | Lista de produtos sem data de criação e sem busca | Baixo — difícil encontrar produto em volume |

---

## Sumário Executivo

| ID | Tipo | Descrição | Esforço |
|---|---|---|---|
| S06-01 | feat | Progress steps no pipeline (Upload → Detectando → Gerando → Revisão) | Médio |
| S06-02 | feat | Toast de notificação global (sucesso, erro, info) | Pequeno |
| S06-03 | feat | Tratamento de erros em todas as chamadas de API | Médio |
| S06-04 | feat | Badge de view (Frente/Costas/etc) nos cards de resultado | Pequeno |
| S06-05 | feat | Modal de confirmação antes de executar pipeline com custo estimado | Pequeno |
| S06-06 | feat | Loading skeleton na lista de produtos | Pequeno |
| S06-07 | feat | Polling de status do job com progresso visual | Médio |

---

## S06-01 — Progress Steps no Pipeline

### Adicionar componente `PipelineProgress` em `Pipeline.jsx`

```jsx
const STEPS = [
  { id: "upload", label: "Upload", description: "Imagens carregadas" },
  { id: "detecting", label: "Detectando", description: "Analisando regiões protegidas" },
  { id: "generating", label: "Gerando", description: "Criando variações de cor" },
  { id: "review", label: "Revisão", description: "Aprovar resultados" },
];

function PipelineProgress({ currentStep }) {
  const stepIndex = STEPS.findIndex((s) => s.id === currentStep);

  return (
    <div className="flex items-center gap-0 mb-8">
      {STEPS.map((step, i) => {
        const isDone = i < stepIndex;
        const isActive = i === stepIndex;
        const isFuture = i > stepIndex;

        return (
          <div key={step.id} className="flex items-center">
            {/* Step circle */}
            <div className="flex flex-col items-center">
              <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-medium transition-all ${
                isDone ? "bg-emerald-500 text-white" :
                isActive ? "bg-amber-500 text-surface-950 ring-4 ring-amber-500/20" :
                "bg-surface-700 text-neutral-500"
              }`}>
                {isDone ? <Check size={14} /> : i + 1}
              </div>
              <div className="mt-1.5 text-center">
                <p className={`text-xs font-medium ${
                  isActive ? "text-amber-400" :
                  isDone ? "text-emerald-400" :
                  "text-neutral-600"
                }`}>{step.label}</p>
              </div>
            </div>
            {/* Connector */}
            {i < STEPS.length - 1 && (
              <div className={`h-px w-16 mb-5 mx-1 transition-all ${
                i < stepIndex ? "bg-emerald-500" : "bg-surface-600"
              }`} />
            )}
          </div>
        );
      })}
    </div>
  );
}
```

### Integrar no Pipeline — alterar estado `step`

```jsx
// Substituir: const [step, setStep] = useState("upload");
// Por estado mais granular:
const [step, setStep] = useState("upload"); // upload | detecting | generating | review

// No runPipeline:
const runPipeline = async () => {
  setRunning(true);

  setStep("detecting");
  // ... detectProtectedRegions para cada view ...

  setStep("generating");
  // ... createColorVariation para cada view ...

  setStep("review");
  setRunning(false);
};
```

---

## S06-02 — Toast de Notificação Global

### Criar `frontend/src/components/Toast.jsx`

```jsx
import { useState, useEffect, createContext, useContext, useCallback } from "react";
import { Check, X, AlertCircle, Info } from "lucide-react";

const ToastContext = createContext(null);

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);

  const addToast = useCallback((message, type = "info", duration = 4000) => {
    const id = Date.now();
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, duration);
  }, []);

  const removeToast = (id) => setToasts((prev) => prev.filter((t) => t.id !== id));

  return (
    <ToastContext.Provider value={{ toast: addToast }}>
      {children}
      {/* Toast container */}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 pointer-events-none">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`flex items-center gap-3 px-4 py-3 rounded-lg shadow-xl border pointer-events-auto
              animate-in slide-in-from-right-5 duration-300 max-w-sm ${
              t.type === "success" ? "bg-emerald-950 border-emerald-700 text-emerald-300" :
              t.type === "error"   ? "bg-red-950 border-red-800 text-red-300" :
              t.type === "warning" ? "bg-amber-950 border-amber-700 text-amber-300" :
              "bg-surface-800 border-surface-600 text-neutral-200"
            }`}
          >
            {t.type === "success" && <Check size={14} className="shrink-0" />}
            {t.type === "error"   && <AlertCircle size={14} className="shrink-0" />}
            {t.type === "info"    && <Info size={14} className="shrink-0" />}
            <span className="text-sm">{t.message}</span>
            <button
              onClick={() => removeToast(t.id)}
              className="ml-auto opacity-60 hover:opacity-100 transition-opacity"
            >
              <X size={12} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export const useToast = () => useContext(ToastContext);
```

### Integrar no `App.jsx`

```jsx
import { ToastProvider } from "./components/Toast";

// Envolver AuthProvider com ToastProvider:
export default function App() {
  return (
    <ToastProvider>
      <AuthProvider>
        {/* ... routes ... */}
      </AuthProvider>
    </ToastProvider>
  );
}
```

---

## S06-03 — Tratamento de Erros em Todas as Chamadas

### Padrão de chamada com toast em `Pipeline.jsx`

```jsx
import { useToast } from "../components/Toast";

// Dentro do componente Pipeline:
const { toast } = useToast();

const handleUpload = async (view, file) => {
  try {
    const res = await uploadImage(productId, file, view);
    setImages((prev) => ({ ...prev, [view]: res.data.data }));
    toast(`${VIEW_LABELS[view]} carregada`, "success");
  } catch (err) {
    const msg = err.response?.data?.detail || "Erro ao fazer upload";
    toast(msg, "error");
  }
};

const runPipeline = async () => {
  if (!productId) return;
  setRunning(true);
  setStep("detecting");
  const allJobs = [];

  try {
    for (const view of VIEWS) {
      const img = images[view];
      if (!img) continue;

      try {
        await detectProtectedRegions(img.id);
      } catch {
        toast(`Detecção falhou para ${VIEW_LABELS[view]} — continuando`, "warning");
      }
    }

    setStep("generating");

    for (const view of VIEWS) {
      const img = images[view];
      if (!img) continue;

      try {
        const res = await createColorVariation(img.id, colors);
        if (res?.data?.data?.results) {
          allJobs.push(...res.data.data.results);
        }
      } catch {
        toast(`Geração falhou para ${VIEW_LABELS[view]}`, "error");
      }
    }

    if (allJobs.length === 0) {
      toast("Nenhuma variação gerada. Verifique as imagens.", "error");
      setStep("upload");
      return;
    }

    setJobs(allJobs);
    setStep("review");
    toast(`${allJobs.length} variações geradas com sucesso`, "success");

  } finally {
    setRunning(false);
  }
};

const handleApprove = async (jobId) => {
  try {
    await approveJob(jobId);
    setJobs((prev) => prev.map((j) => j.job_id === jobId ? { ...j, status: "approved" } : j));
    toast("Aprovado", "success");
  } catch {
    toast("Erro ao aprovar", "error");
  }
};

const handleReject = async (jobId) => {
  try {
    await rejectJob(jobId, "Rejeitado pelo operador");
    setJobs((prev) => prev.map((j) => j.job_id === jobId ? { ...j, status: "rejected" } : j));
    toast("Rejeitado", "info");
  } catch {
    toast("Erro ao rejeitar", "error");
  }
};
```

### Tratamento de erro no `Produtos.jsx`

```jsx
const { toast } = useToast();

const handleCreate = async (e) => {
  e.preventDefault();
  setSubmitting(true);
  try {
    await createProduct(form);
    const r = await listProducts();
    setProducts(r.data.data);
    setShowForm(false);
    setForm({ name: "", category: "", fabric: "", notes: "" });
    toast("Produto criado com sucesso", "success");
  } catch (err) {
    const msg = err.response?.data?.detail || "Erro ao criar produto";
    toast(msg, "error");
  } finally {
    setSubmitting(false);
  }
};
```

---

## S06-04 — Badge de View nos Cards de Resultado

### Alterar `JobCard` — adicionar badge da view

```jsx
// No retorno do job, incluir view no payload (via API)
// No JobCard, exibir badge:

<div className="absolute top-2 right-2">
  {job.view && (
    <span className="text-xs bg-black/50 text-white px-2 py-0.5 rounded font-mono">
      {VIEW_LABELS[job.view] || job.view}
    </span>
  )}
</div>
```

### Alterar `backend/app/api/jobs.py` — incluir `view` no resultado

```python
# No endpoint color-variation, incluir view no resultado:
results.append({
    "job_id": str(job.id),
    "color_hex": color_hex,
    "status": "pending_review",
    "png_url": result["png_url"],
    "jpg_url": result["jpg_url"],
    "cost_cents": result["cost_cents"],
    "method": result.get("method", "gemini"),
    "view": image.view,   # ← adicionar
})
```

---

## S06-05 — Modal de Confirmação com Custo Estimado

### Adicionar `ConfirmModal` em `Pipeline.jsx`

```jsx
function ConfirmModal({ uploadedCount, colorCount, onConfirm, onCancel }) {
  const totalJobs = uploadedCount * colorCount;
  const estimatedCost = totalJobs * 3; // 3¢ por job Gemini

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-40">
      <div className="bg-surface-800 border border-surface-600 rounded-xl p-6 max-w-sm w-full mx-4">
        <h2 className="font-display text-lg text-neutral-100 mb-1">Confirmar pipeline</h2>
        <p className="text-sm text-neutral-400 mb-4">
          Serão geradas {totalJobs} variações de cor.
        </p>

        <div className="bg-surface-700 rounded-lg p-4 mb-4 space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-neutral-400">Views selecionadas</span>
            <span className="text-neutral-100">{uploadedCount}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-neutral-400">Cores alvo</span>
            <span className="text-neutral-100">{colorCount}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-neutral-400">Total de jobs</span>
            <span className="text-neutral-100">{totalJobs}</span>
          </div>
          <div className="border-t border-surface-600 pt-2 flex justify-between text-sm">
            <span className="text-neutral-400">Custo estimado</span>
            <span className="text-amber-400 font-medium">~{estimatedCost}¢ (~R${(estimatedCost * 0.006).toFixed(2)})</span>
          </div>
        </div>

        <div className="flex gap-3">
          <button
            onClick={onConfirm}
            className="flex-1 py-2.5 bg-amber-500 hover:bg-amber-400 text-surface-950 rounded-lg text-sm font-medium transition-colors"
          >
            Executar
          </button>
          <button
            onClick={onCancel}
            className="flex-1 py-2.5 bg-surface-700 hover:bg-surface-600 text-neutral-300 rounded-lg text-sm transition-colors"
          >
            Cancelar
          </button>
        </div>
      </div>
    </div>
  );
}
```

### Integrar no botão de execução

```jsx
const [showConfirm, setShowConfirm] = useState(false);

// Substituir onClick do botão:
onClick={() => setShowConfirm(true)}

// Adicionar modal condicional antes do fechamento do return:
{showConfirm && (
  <ConfirmModal
    uploadedCount={uploadedCount}
    colorCount={colors.length}
    onConfirm={() => { setShowConfirm(false); runPipeline(); }}
    onCancel={() => setShowConfirm(false)}
  />
)}
```

---

## S06-06 — Loading Skeleton na Lista de Produtos

### Alterar `Produtos.jsx`

```jsx
// Substituir loading state:
{loading ? (
  <div className="space-y-2">
    {[1, 2, 3].map((i) => (
      <div key={i} className="bg-surface-800 border border-surface-700 rounded-lg px-5 py-4 animate-pulse">
        <div className="flex items-center gap-4">
          <div className="w-8 h-8 bg-surface-700 rounded" />
          <div className="space-y-2">
            <div className="h-3 w-40 bg-surface-700 rounded" />
            <div className="h-2 w-24 bg-surface-700 rounded" />
          </div>
        </div>
      </div>
    ))}
  </div>
) : /* lista normal */}
```

---

## S06-07 — Polling de Status do Job

Para jobs que demoram mais, o frontend deve consultar o status periodicamente até `done` ou `failed`.

### Utilitário `pollJob` em `frontend/src/services/api.js`

```javascript
export const pollJob = (jobId, onUpdate, maxAttempts = 30, intervalMs = 2000) =>
  new Promise((resolve, reject) => {
    let attempts = 0;
    const interval = setInterval(async () => {
      attempts++;
      try {
        const res = await getJob(jobId);
        const job = res.data.data;
        onUpdate(job);
        if (job.status === "done" || job.status === "pending_review" ||
            job.status === "failed") {
          clearInterval(interval);
          resolve(job);
        }
        if (attempts >= maxAttempts) {
          clearInterval(interval);
          reject(new Error("Timeout aguardando job"));
        }
      } catch (err) {
        clearInterval(interval);
        reject(err);
      }
    }, intervalMs);
  });
```

---

## S06-08 — Página de Resultados (Histórico de Jobs)

**Motivação crítica:** o operador pode navegar acidentalmente para fora do pipeline durante a geração e perder acesso aos resultados. A página de Resultados permite recuperar qualquer trabalho gerado anteriormente.

### Novo endpoint no backend — `GET /api/v1/jobs`

Listar todos os jobs de um produto com seus resultados:

```python
# Adicionar em backend/app/api/jobs.py

@router.get("")
def list_jobs(
    product_id: str | None = None,
    type: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    query = db.query(GenerationJob)

    if product_id:
        # Filtrar jobs pelo product_id via join com ProductImage
        query = query.join(ProductImage).filter(
            ProductImage.product_id == product_id
        )
    if type:
        query = query.filter(GenerationJob.type == type)
    if status:
        query = query.filter(GenerationJob.status == status)

    jobs = query.order_by(GenerationJob.created_at.desc()).limit(100).all()

    return StandardResponse(data=[
        {
            "id": str(j.id),
            "type": j.type.value,
            "status": j.status.value,
            "api_used": j.api_used,
            "cost_cents": j.cost_cents,
            "result": json.loads(j.result) if j.result else None,
            "created_at": j.created_at.isoformat(),
            "completed_at": j.completed_at.isoformat() if j.completed_at else None,
            "product_id": str(j.product_image.product_id) if j.product_image else None,
            "view": j.product_image.view if j.product_image else None,
        }
        for j in jobs
    ])
```

### Adicionar em `frontend/src/services/api.js`

```javascript
export const listJobs = (productId = null, type = null, status = null) => {
  const params = {};
  if (productId) params.product_id = productId;
  if (type) params.type = type;
  if (status) params.status = status;
  return api.get("/jobs", { params });
};
```

### Nova página `frontend/src/pages/Resultados.jsx`

```jsx
import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Check, X, Clock, ArrowLeft, RefreshCw } from "lucide-react";
import { listJobs, approveJob, rejectJob, getProduct } from "../services/api";
import { useToast } from "../components/Toast";

const API_BASE = import.meta.env.VITE_API_URL?.replace("/api/v1", "") || "http://localhost:8002";
const VIEW_LABELS = {
  frente: "Frente", costas: "Costas",
  lat_direita: "Lat. Direita", lat_esquerda: "Lat. Esquerda"
};

export default function Resultados() {
  const { productId } = useParams();
  const navigate = useNavigate();
  const { toast } = useToast();
  const [product, setProduct] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const [prodRes, jobsRes] = await Promise.all([
        getProduct(productId),
        listJobs(productId, "color_variation"),
      ]);
      setProduct(prodRes.data.data);
      setJobs(jobsRes.data.data);
    } catch {
      toast("Erro ao carregar resultados", "error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [productId]);

  const handleApprove = async (jobId) => {
    try {
      await approveJob(jobId);
      setJobs((prev) => prev.map((j) => j.id === jobId ? { ...j, status: "approved" } : j));
      toast("Aprovado", "success");
    } catch { toast("Erro ao aprovar", "error"); }
  };

  const handleReject = async (jobId) => {
    try {
      await rejectJob(jobId, "Rejeitado pelo operador");
      setJobs((prev) => prev.map((j) => j.id === jobId ? { ...j, status: "rejected" } : j));
      toast("Rejeitado", "info");
    } catch { toast("Erro ao rejeitar", "error"); }
  };

  const colorJobs = jobs.filter((j) => j.type === "color_variation");
  const pending = colorJobs.filter((j) => j.status === "pending_review").length;
  const approved = colorJobs.filter((j) => j.status === "approved").length;

  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-center gap-4 mb-8">
        <button
          onClick={() => navigate("/produtos")}
          className="text-neutral-500 hover:text-neutral-300 transition-colors"
        >
          <ArrowLeft size={18} />
        </button>
        <div className="flex-1">
          <p className="text-xs text-neutral-500 uppercase tracking-wider mb-0.5">Resultados</p>
          <h1 className="font-display text-2xl text-neutral-100">
            {product?.name || "Carregando..."}
          </h1>
          {!loading && (
            <p className="text-sm text-neutral-500 mt-1">
              {approved} aprovados · {pending} aguardando revisão · {colorJobs.length} total
            </p>
          )}
        </div>
        <div className="flex gap-2">
          <button
            onClick={load}
            className="flex items-center gap-2 px-3 py-2 bg-surface-700 hover:bg-surface-600 text-neutral-300 rounded-md text-sm transition-colors"
          >
            <RefreshCw size={14} />
            Atualizar
          </button>
          <button
            onClick={() => navigate(`/pipeline/${productId}`)}
            className="flex items-center gap-2 px-4 py-2 bg-amber-500 hover:bg-amber-400 text-surface-950 rounded-md text-sm font-medium transition-colors"
          >
            + Novo pipeline
          </button>
        </div>
      </div>

      {loading ? (
        <div className="grid grid-cols-3 gap-4">
          {[1,2,3,4,5,6].map((i) => (
            <div key={i} className="bg-surface-800 border border-surface-700 rounded-lg overflow-hidden animate-pulse">
              <div className="aspect-square bg-surface-700" />
              <div className="p-3 space-y-2">
                <div className="h-3 w-20 bg-surface-700 rounded" />
              </div>
            </div>
          ))}
        </div>
      ) : colorJobs.length === 0 ? (
        <div className="text-center py-20 text-neutral-600">
          <Clock size={40} className="mx-auto mb-3 opacity-30" />
          <p className="text-sm">Nenhuma variação gerada ainda</p>
          <button
            onClick={() => navigate(`/pipeline/${productId}`)}
            className="mt-4 text-sm text-amber-400 hover:text-amber-300 transition-colors"
          >
            Executar pipeline →
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-3 gap-4">
          {colorJobs.map((job) => {
            const result = job.result;
            const jpgUrl = result?.jpg_url ? `${API_BASE}${result.jpg_url}` : null;
            const colorHex = result?.color_hex || job.result?.color_hex || "#888";

            return (
              <div
                key={job.id}
                className={`bg-surface-800 border rounded-lg overflow-hidden transition-all ${
                  job.status === "approved" ? "border-emerald-500/30" :
                  job.status === "rejected" ? "border-red-500/20 opacity-50" :
                  "border-surface-600"
                }`}
              >
                {/* Imagem */}
                <div className="relative aspect-square bg-surface-700">
                  {jpgUrl ? (
                    <img
                      src={jpgUrl}
                      alt={`Variação`}
                      className="w-full h-full object-contain"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center">
                      <Clock size={24} className="text-neutral-600" />
                    </div>
                  )}
                  {/* Badge view */}
                  {job.view && (
                    <div className="absolute top-2 right-2">
                      <span className="text-xs bg-black/50 text-white px-2 py-0.5 rounded font-mono">
                        {VIEW_LABELS[job.view] || job.view}
                      </span>
                    </div>
                  )}
                </div>

                {/* Info */}
                <div className="p-3">
                  <div className="flex items-center justify-between mb-2">
                    <span className={`text-xs font-medium ${
                      job.status === "approved" ? "text-emerald-400" :
                      job.status === "rejected" ? "text-red-400" :
                      job.status === "pending_review" ? "text-amber-400" :
                      "text-neutral-500"
                    }`}>
                      {job.status === "approved" ? "Aprovado" :
                       job.status === "rejected" ? "Rejeitado" :
                       job.status === "pending_review" ? "Aguardando revisão" :
                       job.status}
                    </span>
                    <span className="text-xs text-neutral-600 font-mono">
                      {job.cost_cents}¢
                    </span>
                  </div>

                  {job.status === "pending_review" && (
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleApprove(job.id)}
                        className="flex-1 flex items-center justify-center gap-1 py-1.5 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 rounded text-xs transition-colors"
                      >
                        <Check size={12} /> Aprovar
                      </button>
                      <button
                        onClick={() => handleReject(job.id)}
                        className="flex-1 flex items-center justify-center gap-1 py-1.5 bg-red-500/10 hover:bg-red-500/20 text-red-400 rounded text-xs transition-colors"
                      >
                        <X size={12} /> Rejeitar
                      </button>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
```

### Atualizar `App.jsx` — adicionar rota de resultados

```jsx
import Resultados from "./pages/Resultados";

// Adicionar dentro das rotas protegidas:
<Route path="resultados/:productId" element={<Resultados />} />
```

### Atualizar `Layout.jsx` — adicionar item na sidebar

```jsx
import { Package, Zap, History } from "lucide-react";

// navItems não muda — Resultados é acessado via produto, não sidebar direta
// Mas adicionar link "Ver resultados" na página de Pipeline após gerar:
```

### Atualizar `Pipeline.jsx` — link para resultados após geração

```jsx
import { useNavigate } from "react-router-dom";

// No step "review", adicionar botão:
<button
  onClick={() => navigate(`/resultados/${productId}`)}
  className="text-xs text-amber-400 hover:text-amber-300 transition-colors"
>
  Ver histórico completo →
</button>
```

### Atualizar `Produtos.jsx` — botão de resultados por produto

```jsx
// Em cada item da lista, adicionar botão secundário:
<div className="flex items-center gap-2">
  <button
    onClick={(e) => { e.stopPropagation(); navigate(`/resultados/${p.id}`); }}
    className="text-xs text-neutral-500 hover:text-neutral-300 px-2 py-1 rounded hover:bg-surface-600 transition-all"
  >
    Resultados
  </button>
  <ChevronRight size={16} className="text-neutral-600 group-hover:text-neutral-400 transition-colors" />
</div>
```

---

## Ordem de Execução

```
S06-02 (Toast — base para feedback em tudo)
  ↓
S06-03 (Error handling em Pipeline + Produtos)
  ↓
S06-08 backend (GET /api/v1/jobs endpoint)
  ↓
S06-08 frontend (página Resultados + rota + links)
  ↓
S06-01 (Progress steps)
  ↓
S06-05 (Modal de confirmação)
  ↓
S06-04 (Badge de view — backend + frontend)
  ↓
S06-06 (Skeleton loading)
  ↓
S06-07 (Polling utilitário)
```

---

## Commits Atômicos

```
feat(frontend): add global Toast notification system [S06-02]
feat(frontend): add error handling and success feedback to all API calls [S06-03]
feat(api): add GET /jobs endpoint with product_id filter [S06-08]
feat(frontend): add Resultados page with job history and approval [S06-08]
feat(frontend): add pipeline progress steps indicator [S06-01]
feat(frontend): add confirmation modal with cost estimate before pipeline [S06-05]
feat(frontend): add view badge to job result cards [S06-04]
feat(frontend): add skeleton loading for product list [S06-06]
feat(frontend): add pollJob utility for async job status [S06-07]
feat(api): include view field in color variation job results [S06-04]
```

---

## Critérios de Aceite

- [ ] Toast verde aparece após upload de imagem
- [ ] Toast vermelho aparece se API retornar erro
- [ ] Steps visuais mudam conforme pipeline avança (Detectando → Gerando → Revisão)
- [ ] Modal de confirmação mostra custo estimado antes de executar
- [ ] Cards de resultado têm badge indicando a view (Frente, Costas, etc)
- [ ] Lista de produtos mostra skeleton animado durante carregamento
- [ ] Erro de rede no login mostra mensagem legível, não tela em branco
- [ ] Página de Resultados mostra todos os jobs gerados para o produto
- [ ] Aprovar/rejeitar funciona direto na página de Resultados
- [ ] Botão "Resultados" aparece em cada produto na listagem
- [ ] Após pipeline rodar, link "Ver histórico completo" aparece na tela de revisão
- [ ] Navegar para fora e voltar via "Resultados" recupera todo o trabalho anterior
