import { useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import { Upload, Zap, Eye, Check, X, Loader } from "lucide-react";
import {
  getProduct, uploadImage, detectProtectedRegions,
  createColorVariation, getJob, approveJob, rejectJob
} from "../services/api";

const VIEWS = ["frente", "costas", "lat_direita", "lat_esquerda"];
const VIEW_LABELS = { frente: "Frente", costas: "Costas", lat_direita: "Lat. Direita", lat_esquerda: "Lat. Esquerda" };
const DEFAULT_COLORS = ["#696980", "#978b7b", "#9e987d"];

export default function Pipeline() {
  const { productId } = useParams();
  const [product, setProduct] = useState(null);
  const [images, setImages] = useState({}); // { view: imageData }
  const [colors, setColors] = useState(DEFAULT_COLORS);
  const [colorInput, setColorInput] = useState("");
  const [jobs, setJobs] = useState([]);
  const [running, setRunning] = useState(false);
  const [step, setStep] = useState("upload"); // upload | running | review

  useEffect(() => {
    if (productId) getProduct(productId).then((r) => setProduct(r.data.data));
  }, [productId]);

  const handleUpload = async (view, file) => {
    const res = await uploadImage(productId, file, view);
    setImages((prev) => ({ ...prev, [view]: res.data.data }));
  };

  const runPipeline = async () => {
    setRunning(true);
    setStep("running");
    const allJobs = [];

    for (const view of VIEWS) {
      const img = images[view];
      if (!img) continue;

      // Detectar regioes protegidas
      await detectProtectedRegions(img.id).catch(() => {});

      // Gerar variacoes de cor
      const res = await createColorVariation(img.id, colors).catch(() => null);
      if (res?.data?.data?.results) {
        allJobs.push(...res.data.data.results);
      }
    }

    setJobs(allJobs);
    setStep("review");
    setRunning(false);
  };

  const handleApprove = async (jobId) => {
    await approveJob(jobId);
    setJobs((prev) => prev.map((j) => j.job_id === jobId ? { ...j, status: "approved" } : j));
  };

  const handleReject = async (jobId) => {
    await rejectJob(jobId, "Rejeitado pelo operador");
    setJobs((prev) => prev.map((j) => j.job_id === jobId ? { ...j, status: "rejected" } : j));
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

      {/* Step: Upload */}
      {step === "upload" && (
        <div className="space-y-6">
          {/* Upload das views */}
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

          {/* Cores alvo */}
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

          {/* Botao de execucao */}
          <button
            onClick={runPipeline}
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

      {/* Step: Running */}
      {step === "running" && (
        <div className="flex flex-col items-center justify-center py-24 gap-4">
          <Loader size={32} className="text-amber-400 animate-spin" />
          <p className="text-sm text-neutral-400">Processando pipeline via Gemini...</p>
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
            <button
              onClick={() => setStep("upload")}
              className="text-xs text-neutral-500 hover:text-neutral-300 transition-colors"
            >
              ← Novo pipeline
            </button>
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
    </div>
  );
}

function UploadZone({ view, label, image, onUpload }) {
  const handleDrop = (e) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file) onUpload(file);
  };

  return (
    <label
      className={`relative flex flex-col items-center justify-center aspect-square rounded-lg border-2 border-dashed cursor-pointer transition-all ${
        image
          ? "border-amber-500/50 bg-amber-500/5"
          : "border-surface-600 bg-surface-800 hover:border-surface-500 hover:bg-surface-700"
      }`}
      onDrop={handleDrop}
      onDragOver={(e) => e.preventDefault()}
    >
      <input
        type="file"
        accept="image/png,image/jpeg"
        className="hidden"
        onChange={(e) => e.target.files[0] && onUpload(e.target.files[0])}
      />
      {image ? (
        <>
          <Check size={20} className="text-amber-400 mb-1" />
          <span className="text-xs text-amber-400 font-medium">{label}</span>
          <span className="text-xs text-neutral-600 mt-0.5">Carregado</span>
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

function JobCard({ job, onApprove, onReject }) {
  const statusColors = {
    pending_review: "text-amber-400",
    approved: "text-emerald-400",
    rejected: "text-red-400",
  };

  return (
    <div className={`bg-surface-800 border rounded-lg overflow-hidden transition-all ${
      job.status === "approved" ? "border-emerald-500/30" :
      job.status === "rejected" ? "border-red-500/20 opacity-50" :
      "border-surface-600"
    }`}>
      {/* Preview de cor */}
      <div
        className="h-24 w-full flex items-center justify-center"
        style={{ backgroundColor: job.color_hex }}
      >
        <span className="font-mono text-xs bg-black/30 text-white px-2 py-0.5 rounded">
          {job.color_hex}
        </span>
      </div>

      {/* Info + acoes */}
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
            <button
              onClick={onApprove}
              className="flex-1 flex items-center justify-center gap-1 py-1.5 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 rounded text-xs transition-colors"
            >
              <Check size={12} /> Aprovar
            </button>
            <button
              onClick={onReject}
              className="flex-1 flex items-center justify-center gap-1 py-1.5 bg-red-500/10 hover:bg-red-500/20 text-red-400 rounded text-xs transition-colors"
            >
              <X size={12} /> Rejeitar
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
