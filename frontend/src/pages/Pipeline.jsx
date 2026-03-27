import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Upload, Zap, Check, X, Loader } from "lucide-react";
import {
  getProduct, uploadImage, detectProtectedRegions,
  createColorVariation, getJob, approveJob, rejectJob
} from "../services/api";
import { useToast } from "../components/Toast";

const VIEWS = ["frente", "costas", "lat_direita", "lat_esquerda"];
const VIEW_LABELS = { frente: "Frente", costas: "Costas", lat_direita: "Lat. Direita", lat_esquerda: "Lat. Esquerda" };
const DEFAULT_COLORS = ["#696980", "#978b7b", "#9e987d"];

const STEPS = [
  { id: "upload", label: "Upload", description: "Imagens carregadas" },
  { id: "detecting", label: "Detectando", description: "Analisando regioes protegidas" },
  { id: "generating", label: "Gerando", description: "Criando variacoes de cor" },
  { id: "review", label: "Revisao", description: "Aprovar resultados" },
];

export default function Pipeline() {
  const { productId } = useParams();
  const navigate = useNavigate();
  const { toast } = useToast();
  const [product, setProduct] = useState(null);
  const [images, setImages] = useState({});
  const [colors, setColors] = useState(DEFAULT_COLORS);
  const [colorInput, setColorInput] = useState("");
  const [jobs, setJobs] = useState([]);
  const [running, setRunning] = useState(false);
  const [step, setStep] = useState("upload");
  const [showConfirm, setShowConfirm] = useState(false);

  useEffect(() => {
    if (productId) getProduct(productId).then((r) => setProduct(r.data.data));
  }, [productId]);

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
          toast(`Deteccao falhou para ${VIEW_LABELS[view]} — continuando`, "warning");
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
          toast(`Geracao falhou para ${VIEW_LABELS[view]}`, "error");
        }
      }

      if (allJobs.length === 0) {
        toast("Nenhuma variacao gerada. Verifique as imagens.", "error");
        setStep("upload");
        return;
      }

      setJobs(allJobs);
      setStep("review");
      toast(`${allJobs.length} variacoes geradas`, "success");
      // Redirecionar para Resultados apos 1.5s
      setTimeout(() => navigate(`/resultados/${productId}`), 1500);

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

  const uploadedCount = Object.keys(images).length;

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-8">
        <p className="text-xs text-neutral-500 uppercase tracking-wider mb-1">Pipeline</p>
        <h1 className="font-display text-2xl text-neutral-100">
          {product?.name || "Carregando..."}
        </h1>
        {product && (
          <p className="text-sm text-neutral-500 mt-1">{product.category} · {product.fabric}</p>
        )}
      </div>

      {/* Progress steps */}
      <PipelineProgress currentStep={step} />

      {/* Step: Upload */}
      {step === "upload" && (
        <div className="space-y-6">
          <div>
            <h2 className="text-xs font-medium text-neutral-400 uppercase tracking-wider mb-4">
              1 — Imagens da peca
            </h2>
            <div className="grid grid-cols-4 gap-3">
              {VIEWS.map((view) => (
                <UploadZone
                  key={view}
                  view={view}
                  label={VIEW_LABELS[view]}
                  image={images[view]}
                  onUpload={(file) => handleUpload(view, file)}
                />
              ))}
            </div>
          </div>

          <div>
            <h2 className="text-xs font-medium text-neutral-400 uppercase tracking-wider mb-4">
              2 — Cores alvo
            </h2>
            <div className="flex flex-wrap gap-2 mb-3">
              {colors.map((c) => (
                <div key={c} className="flex items-center gap-2 bg-surface-800 border border-surface-600 rounded px-3 py-1.5">
                  <div className="w-4 h-4 rounded-sm border border-surface-500" style={{ backgroundColor: c }} />
                  <span className="text-xs font-mono text-neutral-300">{c}</span>
                  <button
                    onClick={() => setColors(colors.filter((x) => x !== c))}
                    className="text-neutral-600 hover:text-red-400 transition-colors"
                  >
                    <X size={12} />
                  </button>
                </div>
              ))}
              <div className="flex items-center gap-2">
                <input
                  value={colorInput}
                  onChange={(e) => setColorInput(e.target.value)}
                  placeholder="#RRGGBB"
                  className="bg-surface-700 border border-surface-600 rounded px-3 py-1.5 text-xs font-mono text-neutral-100 w-28 focus:outline-none focus:border-amber-500"
                />
                <button
                  onClick={() => {
                    if (/^#[0-9A-Fa-f]{6}$/.test(colorInput)) {
                      setColors([...colors, colorInput]);
                      setColorInput("");
                    }
                  }}
                  className="px-2 py-1.5 bg-surface-700 hover:bg-surface-600 border border-surface-600 rounded text-xs text-neutral-300 transition-colors"
                >
                  + Add
                </button>
              </div>
            </div>
          </div>

          <button
            onClick={() => setShowConfirm(true)}
            disabled={uploadedCount === 0 || colors.length === 0}
            className="flex items-center gap-2 px-6 py-3 bg-amber-500 hover:bg-amber-400 disabled:opacity-40 disabled:cursor-not-allowed text-surface-950 rounded-md font-medium transition-colors"
          >
            <Zap size={16} />
            Executar pipeline
            {uploadedCount > 0 && (
              <span className="text-xs opacity-70 ml-1">
                ({uploadedCount} view{uploadedCount > 1 ? "s" : ""} × {colors.length} cor{colors.length > 1 ? "es" : ""})
              </span>
            )}
          </button>
        </div>
      )}

      {/* Step: Detecting / Generating */}
      {(step === "detecting" || step === "generating") && (
        <div className="flex flex-col items-center justify-center py-24 gap-4">
          <Loader size={32} className="text-amber-400 animate-spin" />
          <p className="text-sm text-neutral-400">
            {step === "detecting" ? "Analisando regioes protegidas..." : "Gerando variacoes de cor via Gemini..."}
          </p>
          <p className="text-xs text-neutral-600">Isso pode levar alguns segundos por imagem</p>
        </div>
      )}

      {/* Step: Review */}
      {step === "review" && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-medium text-neutral-400 uppercase tracking-wider">
              3 — Revisar e aprovar ({jobs.filter((j) => j.status === "approved").length}/{jobs.length} aprovados)
            </h2>
            <div className="flex items-center gap-4">
              <button
                onClick={() => navigate(`/resultados/${productId}`)}
                className="text-xs text-amber-400 hover:text-amber-300 transition-colors"
              >
                Ver historico completo →
              </button>
              <button
                onClick={() => setStep("upload")}
                className="text-xs text-neutral-500 hover:text-neutral-300 transition-colors"
              >
                ← Novo pipeline
              </button>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-4">
            {jobs.map((job) => (
              <JobCard
                key={job.job_id}
                job={job}
                onApprove={() => handleApprove(job.job_id)}
                onReject={() => handleReject(job.job_id)}
              />
            ))}
          </div>
        </div>
      )}

      {/* Confirm modal */}
      {showConfirm && (
        <ConfirmModal
          uploadedCount={uploadedCount}
          colorCount={colors.length}
          onConfirm={() => { setShowConfirm(false); runPipeline(); }}
          onCancel={() => setShowConfirm(false)}
        />
      )}
    </div>
  );
}

function PipelineProgress({ currentStep }) {
  const stepIndex = STEPS.findIndex((s) => s.id === currentStep);

  return (
    <div className="flex items-center gap-0 mb-8">
      {STEPS.map((step, i) => {
        const isDone = i < stepIndex;
        const isActive = i === stepIndex;

        return (
          <div key={step.id} className="flex items-center">
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

function ConfirmModal({ uploadedCount, colorCount, onConfirm, onCancel }) {
  const totalJobs = uploadedCount * colorCount;
  const estimatedCost = totalJobs * 3;

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-40">
      <div className="bg-surface-800 border border-surface-600 rounded-xl p-6 max-w-sm w-full mx-4">
        <h2 className="font-display text-lg text-neutral-100 mb-1">Confirmar pipeline</h2>
        <p className="text-sm text-neutral-400 mb-4">
          Serao geradas {totalJobs} variacoes de cor.
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

function UploadZone({ view, label, image, onUpload }) {
  const [preview, setPreview] = useState(null);

  const handleFile = (file) => {
    const reader = new FileReader();
    reader.onload = (e) => setPreview(e.target.result);
    reader.readAsDataURL(file);
    onUpload(file);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  };

  return (
    <label
      className={`relative flex flex-col items-center justify-center aspect-square rounded-lg border-2 border-dashed cursor-pointer transition-all overflow-hidden ${
        image
          ? "border-amber-500/50"
          : "border-surface-600 bg-surface-800 hover:border-surface-500 hover:bg-surface-700"
      }`}
      onDrop={handleDrop}
      onDragOver={(e) => e.preventDefault()}
    >
      <input
        type="file"
        accept="image/png,image/jpeg"
        className="hidden"
        onChange={(e) => e.target.files[0] && handleFile(e.target.files[0])}
      />
      {preview ? (
        <>
          <img src={preview} alt={label} className="absolute inset-0 w-full h-full object-contain p-2" />
          <div className="absolute bottom-0 left-0 right-0 bg-black/60 py-1 px-2 flex items-center justify-between">
            <span className="text-xs text-amber-400 font-medium">{label}</span>
            <Check size={12} className="text-amber-400" />
          </div>
        </>
      ) : (
        <>
          <Upload size={20} className="text-neutral-600 mb-1" />
          <span className="text-xs text-neutral-500">{label}</span>
        </>
      )}
    </label>
  );
}

const API_BASE = import.meta.env.VITE_API_URL?.replace("/api/v1", "") || "http://localhost:8002";

function JobCard({ job, onApprove, onReject }) {
  const statusColors = {
    pending_review: "text-amber-400",
    approved: "text-emerald-400",
    rejected: "text-red-400",
  };

  const imageUrl = job.jpg_url ? `${API_BASE}${job.jpg_url}` : null;

  return (
    <div className={`bg-surface-800 border rounded-lg overflow-hidden transition-all ${
      job.status === "approved" ? "border-emerald-500/30" :
      job.status === "rejected" ? "border-red-500/20 opacity-50" :
      "border-surface-600"
    }`}>
      <div className="relative aspect-square bg-surface-700">
        {imageUrl ? (
          <img
            src={imageUrl}
            alt={`Variacao ${job.color_hex}`}
            className="w-full h-full object-contain"
            onError={(e) => {
              e.target.style.display = "none";
              e.target.nextSibling.style.display = "flex";
            }}
          />
        ) : null}
        <div
          className="absolute inset-0 flex items-center justify-center"
          style={{ backgroundColor: job.color_hex, display: imageUrl ? "none" : "flex" }}
        >
          <span className="font-mono text-xs bg-black/30 text-white px-2 py-0.5 rounded">{job.color_hex}</span>
        </div>
        {/* Badge view */}
        {job.view && (
          <div className="absolute top-2 right-2">
            <span className="text-xs bg-black/50 text-white px-2 py-0.5 rounded font-mono">
              {VIEW_LABELS[job.view] || job.view}
            </span>
          </div>
        )}
        <div className="absolute bottom-2 left-2">
          <span
            className="font-mono text-xs px-2 py-0.5 rounded border"
            style={{ backgroundColor: job.color_hex + "33", borderColor: job.color_hex + "66", color: "#fff" }}
          >
            {job.color_hex}
          </span>
        </div>
      </div>

      <div className="p-3">
        <div className="flex items-center justify-between mb-2">
          <span className={`text-xs font-medium ${statusColors[job.status] || "text-neutral-400"}`}>
            {job.status === "pending_review" ? "Aguardando revisao" :
             job.status === "approved" ? "Aprovado" : "Rejeitado"}
          </span>
          <span className="text-xs text-neutral-600 font-mono">{job.cost_cents}¢</span>
        </div>
        {job.status === "pending_review" && (
          <div className="flex gap-2">
            <button onClick={onApprove} className="flex-1 flex items-center justify-center gap-1 py-1.5 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 rounded text-xs transition-colors">
              <Check size={12} /> Aprovar
            </button>
            <button onClick={onReject} className="flex-1 flex items-center justify-center gap-1 py-1.5 bg-red-500/10 hover:bg-red-500/20 text-red-400 rounded text-xs transition-colors">
              <X size={12} /> Rejeitar
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
