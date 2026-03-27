# PRD — Sprint 08: Histórico Completo de Execuções

**Status:** Aprovação Pendente
**Origem:** Demanda de rastreabilidade total — ver tudo de ponta a ponta
**Data:** 2026-03-26
**Objetivo:** Página de histórico que mostra cada execução com prompt, imagem de entrada, imagem de saída, custo, tempo, erros e fallbacks. Request/response bruto da IA armazenado em tabela separada no banco para auditoria.

---

## O que o usuário quer ver no frontend

| Campo | Descrição |
|---|---|
| Prompt enviado | Texto exato enviado ao Claude ou Gemini |
| Imagem de entrada | Thumbnail da imagem original enviada |
| Imagem de saída | Imagem gerada pelo modelo |
| Custo | Em centavos e em reais (R$) |
| Tempo de execução | Em milissegundos |
| Erros / fallbacks | Se houve erro, qual foi; se usou Pillow fallback |
| Metadados | Status, view, cor HEX, produto, modelo usado, data |

## O que vai só no banco (não no frontend)

- Request completo (payload enviado à API da IA)
- Response completo (JSON bruto retornado pela IA)
- Armazenado em tabela `job_api_logs` separada

---

## Sumário Executivo

| ID | Tipo | Descrição | Esforço |
|---|---|---|---|
| S08-01 | feat | Migration: tabela `job_api_logs` + campos de tempo/prompt em `generation_jobs` | Médio |
| S08-02 | feat | Backend: capturar prompt, tempo e log de API em cada chamada | Médio |
| S08-03 | feat | Backend: endpoint `GET /jobs/history` com todos os dados | Médio |
| S08-04 | feat | Frontend: página Histórico na sidebar | Médio |
| S08-05 | feat | Frontend: card de execução expandível com todos os dados | Médio |

---

## S08-01 — Migration: Novos campos e tabela `job_api_logs`

### `backend/app/migrations/migrate_sprint_08.py`

```python
"""
Migration Sprint 08 — Adiciona campos de rastreabilidade em generation_jobs
e cria tabela job_api_logs.
Idempotente.
"""
import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://confexai:confexai@localhost/confexai_db")
engine = create_engine(DATABASE_URL)


def add_column_if_not_exists(conn, table, column, definition):
    result = conn.execute(text(
        f"SELECT column_name FROM information_schema.columns "
        f"WHERE table_name='{table}' AND column_name='{column}'"
    ))
    if not result.fetchone():
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))
        print(f"✅ Coluna '{column}' adicionada em {table}.")
    else:
        print(f"✅ Coluna '{column}' já existe em {table}.")


def migrate():
    with engine.begin() as conn:
        # Campos novos em generation_jobs
        add_column_if_not_exists(conn, "generation_jobs", "prompt_used", "TEXT NULL")
        add_column_if_not_exists(conn, "generation_jobs", "model_used", "VARCHAR(100) NULL")
        add_column_if_not_exists(conn, "generation_jobs", "duration_ms", "INTEGER NULL")
        add_column_if_not_exists(conn, "generation_jobs", "input_image_url", "VARCHAR(500) NULL")
        add_column_if_not_exists(conn, "generation_jobs", "fallback_reason", "TEXT NULL")

        # Tabela de logs de API (request/response brutos)
        result = conn.execute(text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
            "WHERE table_schema='public' AND table_name='job_api_logs')"
        ))
        if not result.scalar():
            conn.execute(text("""
                CREATE TABLE job_api_logs (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    job_id UUID NOT NULL REFERENCES generation_jobs(id) ON DELETE CASCADE,
                    request_payload TEXT,
                    response_payload TEXT,
                    http_status INTEGER,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """))
            print("✅ Tabela 'job_api_logs' criada.")
        else:
            print("✅ Tabela 'job_api_logs' já existe.")


if __name__ == "__main__":
    migrate()
```

### Atualizar `backend/app/models.py`

```python
class GenerationJob(Base):
    __tablename__ = "generation_jobs"
    # ... campos existentes ...
    prompt_used = Column(Text, nullable=True)           # prompt exato enviado
    model_used = Column(String(100), nullable=True)     # ex: gemini-2.0-flash-exp
    duration_ms = Column(Integer, nullable=True)        # tempo de execução em ms
    input_image_url = Column(String(500), nullable=True) # URL da imagem de entrada
    fallback_reason = Column(Text, nullable=True)       # motivo do fallback se houver


class JobApiLog(Base):
    __tablename__ = "job_api_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("generation_jobs.id", ondelete="CASCADE"), nullable=False)
    request_payload = Column(Text, nullable=True)   # JSON do request enviado
    response_payload = Column(Text, nullable=True)  # JSON do response recebido
    http_status = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("GenerationJob", backref="api_logs")
```

---

## S08-02 — Capturar Dados em Cada Chamada de IA

### Atualizar `backend/app/services/color_variation.py`

```python
import time

def _apply_via_gemini(image_bytes, target_hex, protected_regions, output_path) -> dict:
    from google import genai
    from google.genai import types
    import os, base64, json

    client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
    img = Image.open(io.BytesIO(image_bytes))
    width, height = img.size

    prompt = COLOR_VARIATION_PROMPT.format(color_hex=target_hex)

    start_ms = int(time.time() * 1000)

    response = client.models.generate_content(
        model="gemini-2.0-flash-exp",
        contents=[
            types.Part.from_text(text=prompt),
            types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
        ],
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
        ),
    )

    duration_ms = int(time.time() * 1000) - start_ms

    # Extrair imagem
    result_bytes = None
    for part in response.candidates[0].content.parts:
        if part.inline_data is not None:
            result_bytes = part.inline_data.data
            break

    if result_bytes is None:
        raise ValueError("Gemini não retornou imagem na resposta")

    result = _save_result(result_bytes, output_path, width, height)
    result["prompt_used"] = prompt
    result["model_used"] = "gemini-2.0-flash-exp"
    result["duration_ms"] = duration_ms

    # Log do request/response para auditoria (sem bytes de imagem)
    result["api_log"] = {
        "request_payload": json.dumps({
            "model": "gemini-2.0-flash-exp",
            "prompt": prompt,
            "image_size_bytes": len(image_bytes),
            "response_modalities": ["IMAGE", "TEXT"],
        }),
        "response_payload": json.dumps({
            "candidates_count": len(response.candidates),
            "has_image": result_bytes is not None,
            "duration_ms": duration_ms,
        }),
        "http_status": 200,
    }

    return result


def _apply_via_pillow(image_bytes, target_hex, output_path) -> dict:
    import time
    start_ms = int(time.time() * 1000)
    # ... lógica existente ...
    duration_ms = int(time.time() * 1000) - start_ms

    result = _save_result(result_bytes, output_path, width, height)
    result["prompt_used"] = f"Pillow color tint: {target_hex}"
    result["model_used"] = "pillow_fallback"
    result["duration_ms"] = duration_ms
    result["api_log"] = None
    return result
```

### Atualizar `backend/app/services/protected_regions.py`

```python
import time

def detect_protected_regions(image_bytes: bytes) -> dict:
    # ... código existente ...
    start_ms = int(time.time() * 1000)

    response = client.messages.create(...)

    duration_ms = int(time.time() * 1000) - start_ms
    raw = response.content[0].text.strip()
    result = json.loads(raw)

    # Adicionar dados de rastreabilidade
    result["prompt_used"] = DETECTION_PROMPT.format(width=width, height=height)
    result["model_used"] = "claude-sonnet-4-20250514"
    result["duration_ms"] = duration_ms
    result["api_log"] = {
        "request_payload": json.dumps({
            "model": "claude-sonnet-4-20250514",
            "prompt_preview": DETECTION_PROMPT[:200],
            "image_size_bytes": len(image_bytes),
            "max_tokens": 1024,
        }),
        "response_payload": json.dumps({
            "has_protected_regions": result.get("has_protected_regions"),
            "regions_count": len(result.get("protected_regions", [])),
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "duration_ms": duration_ms,
        }),
        "http_status": 200,
    }
    return result
```

### Atualizar `backend/app/api/jobs.py` — salvar campos novos

```python
# No endpoint color-variation, após a geração:
job.prompt_used = result.get("prompt_used")
job.model_used = result.get("model_used")
job.duration_ms = result.get("duration_ms")
job.input_image_url = path_to_url(image_path)

# Se houve fallback:
if result.get("method") == "pillow_fallback":
    job.fallback_reason = "Gemini retornou erro — usado fallback Pillow"

# Salvar log de API
api_log_data = result.get("api_log")
if api_log_data:
    from app.models import JobApiLog
    api_log = JobApiLog(
        job_id=job.id,
        request_payload=api_log_data.get("request_payload"),
        response_payload=api_log_data.get("response_payload"),
        http_status=api_log_data.get("http_status", 200),
    )
    db.add(api_log)

db.commit()
```

---

## S08-03 — Endpoint `GET /jobs/history`

```python
@router.get("/history")
def get_history(
    product_id: str | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """
    Retorna histórico completo de execuções com todos os dados de rastreabilidade.
    """
    from app.models import Product

    query = db.query(GenerationJob).order_by(GenerationJob.created_at.desc())

    if product_id:
        query = query.join(ProductImage).filter(
            ProductImage.product_id == product_id
        )

    jobs = query.limit(limit).all()

    result = []
    for j in jobs:
        pid = str(j.product_image.product_id) if j.product_image else None
        product_name = None
        if pid:
            prod = db.query(Product).filter(Product.id == pid).first()
            product_name = prod.name if prod else None

        job_result = json.loads(j.result) if j.result else {}

        result.append({
            # Identidade
            "id": str(j.id),
            "product_id": pid,
            "product_name": product_name,
            "view": j.product_image.view if j.product_image else None,

            # Tipo e status
            "type": j.type.value,
            "status": j.status.value,
            "is_archived": j.is_archived,

            # IA
            "api_used": j.api_used,
            "model_used": j.model_used,
            "prompt_used": j.prompt_used,

            # Imagens
            "input_image_url": j.input_image_url,
            "output_jpg_url": job_result.get("jpg_url"),
            "output_png_url": job_result.get("png_url"),
            "color_hex": job_result.get("color_hex"),

            # Custo e performance
            "cost_cents": j.cost_cents,
            "cost_brl": round((j.cost_cents or 0) * 0.006, 4),
            "tokens_used": j.tokens_used,
            "duration_ms": j.duration_ms,

            # Erros
            "error_message": j.error_message,
            "fallback_reason": j.fallback_reason,
            "method": job_result.get("method"),

            # Timestamps
            "created_at": j.created_at.isoformat(),
            "completed_at": j.completed_at.isoformat() if j.completed_at else None,
        })

    return StandardResponse(data=result)
```

---

## S08-04 — Frontend: Página Histórico

### Adicionar em `frontend/src/components/Layout.jsx`

```jsx
import { Package, Images, Zap, ScrollText } from "lucide-react";

const navItems = [
  { to: "/produtos", icon: Package, label: "Produtos" },
  { to: "/resultados", icon: Images, label: "Resultados" },
  { to: "/historico", icon: ScrollText, label: "Histórico" },
  { to: "/pipeline", icon: Zap, label: "Novo Pipeline" },
];
```

### Adicionar rota em `frontend/src/App.jsx`

```jsx
import Historico from "./pages/Historico";
// ...
<Route path="historico" element={<Historico />} />
```

### Adicionar em `frontend/src/services/api.js`

```javascript
export const getHistory = (productId = null, limit = 50) => {
  const params = { limit };
  if (productId) params.product_id = productId;
  return api.get("/jobs/history", { params });
};
```

---

## S08-05 — Frontend: `frontend/src/pages/Historico.jsx`

```jsx
import { useState, useEffect } from "react";
import { ChevronDown, ChevronRight, Clock, Zap, AlertTriangle, Check, X } from "lucide-react";
import { getHistory } from "../services/api";
import { useToast } from "../components/Toast";

const API_BASE = import.meta.env.VITE_API_URL?.replace("/api/v1", "") || "http://localhost:8002";

const TYPE_LABELS = {
  color_variation: "Variação de Cor",
  protected_region_detection: "Detecção de Regiões",
  background_removal: "Remoção de Fundo",
  seo_description: "Descrição SEO",
  video_ugc: "Vídeo UGC",
};

const VIEW_LABELS = {
  frente: "Frente", costas: "Costas",
  lat_direita: "Lat. D", lat_esquerda: "Lat. E",
};

const STATUS_STYLES = {
  approved: "text-emerald-400 bg-emerald-500/10",
  rejected: "text-red-400 bg-red-500/10",
  pending_review: "text-amber-400 bg-amber-500/10",
  done: "text-blue-400 bg-blue-500/10",
  failed: "text-red-400 bg-red-500/10",
  processing: "text-neutral-400 bg-surface-600",
};

export default function Historico() {
  const { toast } = useToast();
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(new Set());
  const [filter, setFilter] = useState("all"); // all | color_variation | detection | failed

  useEffect(() => {
    getHistory(null, 100)
      .then((r) => setJobs(r.data.data))
      .catch(() => toast("Erro ao carregar histórico", "error"))
      .finally(() => setLoading(false));
  }, []);

  const toggleExpand = (id) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const filtered = jobs.filter((j) => {
    if (filter === "color_variation") return j.type === "color_variation";
    if (filter === "detection") return j.type === "protected_region_detection";
    if (filter === "failed") return j.status === "failed" || j.error_message;
    return true;
  });

  const totalCost = filtered.reduce((sum, j) => sum + (j.cost_cents || 0), 0);

  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="font-display text-2xl text-neutral-100">Histórico</h1>
          <p className="text-sm text-neutral-500 mt-1">
            {filtered.length} execuções · custo total:{" "}
            <span className="text-amber-400 font-mono">
              {totalCost}¢ (R${(totalCost * 0.006).toFixed(3)})
            </span>
          </p>
        </div>

        {/* Filtros */}
        <div className="flex gap-2">
          {[
            { key: "all", label: "Todos" },
            { key: "color_variation", label: "Variações" },
            { key: "detection", label: "Detecções" },
            { key: "failed", label: "Erros" },
          ].map(({ key, label }) => (
            <button
              key={key}
              onClick={() => setFilter(key)}
              className={`px-3 py-1.5 rounded-md text-xs transition-colors ${
                filter === key
                  ? "bg-amber-500/10 text-amber-400 border border-amber-500/30"
                  : "bg-surface-700 text-neutral-400 border border-surface-600 hover:text-neutral-200"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="space-y-2">
          {[1,2,3,4,5].map((i) => (
            <div key={i} className="bg-surface-800 border border-surface-700 rounded-lg h-14 animate-pulse" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-20 text-neutral-600">
          <Clock size={40} className="mx-auto mb-3 opacity-30" />
          <p className="text-sm">Nenhuma execução encontrada</p>
        </div>
      ) : (
        <div className="space-y-2">
          {filtered.map((job) => {
            const isExpanded = expanded.has(job.id);
            const hasError = job.error_message || job.fallback_reason;
            const inputUrl = job.input_image_url ? `${API_BASE}${job.input_image_url}` : null;
            const outputUrl = job.output_jpg_url ? `${API_BASE}${job.output_jpg_url}` : null;

            return (
              <div
                key={job.id}
                className={`bg-surface-800 border rounded-lg overflow-hidden transition-all ${
                  hasError ? "border-red-500/20" : "border-surface-600"
                }`}
              >
                {/* Row header — sempre visível */}
                <button
                  onClick={() => toggleExpand(job.id)}
                  className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-surface-700 transition-colors"
                >
                  {/* Expand icon */}
                  {isExpanded
                    ? <ChevronDown size={14} className="text-neutral-500 shrink-0" />
                    : <ChevronRight size={14} className="text-neutral-500 shrink-0" />
                  }

                  {/* Thumbnail saída */}
                  <div className="w-8 h-8 rounded bg-surface-700 overflow-hidden shrink-0">
                    {outputUrl ? (
                      <img src={outputUrl} className="w-full h-full object-cover" />
                    ) : job.color_hex ? (
                      <div className="w-full h-full" style={{ backgroundColor: job.color_hex }} />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center">
                        <Zap size={12} className="text-neutral-600" />
                      </div>
                    )}
                  </div>

                  {/* Info principal */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-medium text-neutral-200">
                        {TYPE_LABELS[job.type] || job.type}
                      </span>
                      {job.product_name && (
                        <span className="text-xs text-neutral-500">— {job.product_name}</span>
                      )}
                      {job.view && (
                        <span className="text-xs bg-surface-700 text-neutral-400 px-1.5 py-0.5 rounded font-mono">
                          {VIEW_LABELS[job.view] || job.view}
                        </span>
                      )}
                      {job.color_hex && (
                        <span
                          className="text-xs px-1.5 py-0.5 rounded font-mono"
                          style={{ backgroundColor: job.color_hex + "33", color: "#fff" }}
                        >
                          {job.color_hex}
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-3 mt-0.5">
                      <span className="text-xs text-neutral-600 font-mono">
                        {new Date(job.created_at).toLocaleString("pt-BR")}
                      </span>
                      {job.duration_ms && (
                        <span className="text-xs text-neutral-600 font-mono">{job.duration_ms}ms</span>
                      )}
                      {job.model_used && (
                        <span className="text-xs text-neutral-600 font-mono">{job.model_used}</span>
                      )}
                    </div>
                  </div>

                  {/* Status + custo */}
                  <div className="flex items-center gap-3 shrink-0">
                    {hasError && <AlertTriangle size={14} className="text-red-400" />}
                    <span className={`text-xs px-2 py-0.5 rounded font-medium ${STATUS_STYLES[job.status] || "text-neutral-400"}`}>
                      {job.status}
                    </span>
                    {job.cost_cents != null && (
                      <span className="text-xs font-mono text-neutral-500">
                        {job.cost_cents}¢
                      </span>
                    )}
                  </div>
                </button>

                {/* Expanded detail */}
                {isExpanded && (
                  <div className="border-t border-surface-700 px-4 py-4 space-y-4">

                    {/* Imagens lado a lado */}
                    {(inputUrl || outputUrl) && (
                      <div className="grid grid-cols-2 gap-4">
                        {inputUrl && (
                          <div>
                            <p className="text-xs text-neutral-500 uppercase tracking-wider mb-2">Entrada</p>
                            <img
                              src={inputUrl}
                              className="w-full aspect-square object-contain bg-surface-700 rounded-lg"
                            />
                          </div>
                        )}
                        {outputUrl && (
                          <div>
                            <p className="text-xs text-neutral-500 uppercase tracking-wider mb-2">Saída</p>
                            <img
                              src={outputUrl}
                              className="w-full aspect-square object-contain bg-surface-700 rounded-lg"
                            />
                          </div>
                        )}
                      </div>
                    )}

                    {/* Prompt */}
                    {job.prompt_used && (
                      <div>
                        <p className="text-xs text-neutral-500 uppercase tracking-wider mb-2">Prompt enviado</p>
                        <pre className="bg-surface-900 border border-surface-700 rounded-lg p-3 text-xs text-neutral-300 font-mono whitespace-pre-wrap overflow-auto max-h-48">
                          {job.prompt_used}
                        </pre>
                      </div>
                    )}

                    {/* Métricas */}
                    <div className="grid grid-cols-4 gap-3">
                      {[
                        { label: "Custo", value: job.cost_cents != null ? `${job.cost_cents}¢ / R$${(job.cost_cents * 0.006).toFixed(4)}` : "—" },
                        { label: "Tempo", value: job.duration_ms ? `${job.duration_ms}ms` : "—" },
                        { label: "Tokens", value: job.tokens_used || "—" },
                        { label: "Método", value: job.method || job.api_used || "—" },
                      ].map(({ label, value }) => (
                        <div key={label} className="bg-surface-900 rounded-lg p-3">
                          <p className="text-xs text-neutral-500 mb-1">{label}</p>
                          <p className="text-sm font-mono text-neutral-200">{value}</p>
                        </div>
                      ))}
                    </div>

                    {/* Erros / fallback */}
                    {(job.error_message || job.fallback_reason) && (
                      <div className="bg-red-950/30 border border-red-500/20 rounded-lg p-3">
                        <p className="text-xs text-red-400 uppercase tracking-wider mb-1">Erro / Fallback</p>
                        {job.error_message && (
                          <p className="text-xs font-mono text-red-300">{job.error_message}</p>
                        )}
                        {job.fallback_reason && (
                          <p className="text-xs font-mono text-amber-300 mt-1">{job.fallback_reason}</p>
                        )}
                      </div>
                    )}

                    {/* Metadados */}
                    <div className="grid grid-cols-3 gap-3 text-xs">
                      {[
                        { label: "Job ID", value: job.id },
                        { label: "Produto", value: job.product_name || "—" },
                        { label: "View", value: VIEW_LABELS[job.view] || job.view || "—" },
                        { label: "Modelo", value: job.model_used || "—" },
                        { label: "Criado", value: new Date(job.created_at).toLocaleString("pt-BR") },
                        { label: "Concluído", value: job.completed_at ? new Date(job.completed_at).toLocaleString("pt-BR") : "—" },
                      ].map(({ label, value }) => (
                        <div key={label}>
                          <p className="text-neutral-500 mb-0.5">{label}</p>
                          <p className="text-neutral-300 font-mono truncate" title={value}>{value}</p>
                        </div>
                      ))}
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

## Ordem de Execução

```
S08-01 (migration + models)
  ↓
S08-02 (capturar dados nas chamadas de IA)
  ↓
S08-03 (endpoint /history)
  ↓
Rodar migration + testes
  ↓
S08-04 (sidebar + rota)
  ↓
S08-05 (página Histórico)
```

---

## Commits Atômicos

```
feat(db): add prompt_used, model_used, duration_ms, input_image_url, fallback_reason to generation_jobs [S08-01]
feat(db): create job_api_logs table for full request/response audit [S08-01]
feat(api): capture prompt, model, duration and API logs in color variation [S08-02]
feat(api): capture prompt, model, duration and API logs in protected region detection [S08-02]
feat(api): add GET /jobs/history endpoint with full traceability data [S08-03]
feat(frontend): add Histórico to sidebar navigation [S08-04]
feat(frontend): add Historico page with expandable execution cards [S08-05]
```

---

## Critérios de Aceite

- [ ] Migration roda sem erros — 5 novos campos + tabela `job_api_logs`
- [ ] Após rodar pipeline, `generation_jobs.prompt_used` contém o prompt exato
- [ ] `generation_jobs.duration_ms` contém tempo real de execução
- [ ] `generation_jobs.input_image_url` aponta para a imagem enviada
- [ ] `job_api_logs` contém o request/response de cada chamada de IA
- [ ] `GET /jobs/history` retorna todos os campos incluindo prompt, imagens, custo em R$
- [ ] "Histórico" aparece na sidebar
- [ ] Cards mostram thumbnail de entrada e saída lado a lado
- [ ] Prompt completo visível ao expandir
- [ ] Métricas (custo, tempo, tokens, método) em destaque
- [ ] Erros e fallbacks em vermelho/âmbar
- [ ] Filtros por tipo e por erro funcionam
- [ ] Custo total da seleção filtrada visível no header
- [ ] Testes passam sem regressão
