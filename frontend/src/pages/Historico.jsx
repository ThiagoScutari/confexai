import { useState, useEffect } from "react";
import { ChevronDown, ChevronRight, Clock, Zap, AlertTriangle, Check, X } from "lucide-react";
import { getHistory } from "../services/api";
import { useToast } from "../components/Toast";
import { SkeletonRow } from "../components/Skeleton";

const API_BASE = import.meta.env.VITE_API_URL?.replace("/api/v1", "") || "http://localhost:8002";

const TYPE_LABELS = {
  color_variation: "Variacao de Cor",
  protected_region_detection: "Deteccao de Regioes",
  background_removal: "Remocao de Fundo",
  seo_description: "Descricao SEO",
  video_ugc: "Video UGC",
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
  const [filter, setFilter] = useState("all");

  useEffect(() => {
    getHistory(null, 100)
      .then((r) => setJobs(r.data.data))
      .catch(() => toast("Erro ao carregar historico", "error"))
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
          <h1 className="font-display text-2xl text-neutral-100">Historico</h1>
          <p className="text-sm text-neutral-500 mt-1">
            {filtered.length} execucoes · custo total:{" "}
            <span className="text-amber-400 font-mono">
              {totalCost}c (R${(totalCost * 0.006).toFixed(3)})
            </span>
          </p>
        </div>

        {/* Filtros */}
        <div className="flex gap-2">
          {[
            { key: "all", label: "Todos" },
            { key: "color_variation", label: "Variacoes" },
            { key: "detection", label: "Deteccoes" },
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
            <SkeletonRow key={i} />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-20 text-neutral-600">
          <Clock size={40} className="mx-auto mb-3 opacity-30" />
          <p className="text-sm">Nenhuma execucao encontrada</p>
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
                {/* Row header */}
                <button
                  onClick={() => toggleExpand(job.id)}
                  className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-surface-700 transition-colors"
                >
                  {isExpanded
                    ? <ChevronDown size={14} className="text-neutral-500 shrink-0" />
                    : <ChevronRight size={14} className="text-neutral-500 shrink-0" />
                  }

                  {/* Thumbnail */}
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

                  {/* Info */}
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
                        {job.cost_cents}c
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
                            <p className="text-xs text-neutral-500 uppercase tracking-wider mb-2">Saida</p>
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

                    {/* Metricas */}
                    <div className="grid grid-cols-4 gap-3">
                      {[
                        { label: "Custo", value: job.cost_cents != null ? `${job.cost_cents}c / R$${(job.cost_cents * 0.006).toFixed(4)}` : "—" },
                        { label: "Tempo", value: job.duration_ms ? `${job.duration_ms}ms` : "—" },
                        { label: "Tokens", value: job.tokens_used || "—" },
                        { label: "Metodo", value: job.method || job.api_used || "—" },
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
                        { label: "Concluido", value: job.completed_at ? new Date(job.completed_at).toLocaleString("pt-BR") : "—" },
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
