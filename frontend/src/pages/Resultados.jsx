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
              {approved} aprovados · {pending} aguardando revisao · {colorJobs.length} total
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
          <p className="text-sm">Nenhuma variacao gerada ainda</p>
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
            const colorHex = result?.color_hex || "#888";

            return (
              <div
                key={job.id}
                className={`bg-surface-800 border rounded-lg overflow-hidden transition-all ${
                  job.status === "approved" ? "border-emerald-500/30" :
                  job.status === "rejected" ? "border-red-500/20 opacity-50" :
                  "border-surface-600"
                }`}
              >
                <div className="relative aspect-square bg-surface-700">
                  {jpgUrl ? (
                    <img
                      src={jpgUrl}
                      alt={`Variacao`}
                      className="w-full h-full object-contain"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center">
                      <Clock size={24} className="text-neutral-600" />
                    </div>
                  )}
                  {job.view && (
                    <div className="absolute top-2 right-2">
                      <span className="text-xs bg-black/50 text-white px-2 py-0.5 rounded font-mono">
                        {VIEW_LABELS[job.view] || job.view}
                      </span>
                    </div>
                  )}
                </div>

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
                       job.status === "pending_review" ? "Aguardando revisao" :
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
