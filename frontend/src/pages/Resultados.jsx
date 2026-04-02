import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  ChevronDown, ChevronRight, Download, Archive, ArchiveRestore,
  Check, X, RefreshCw, Package, Images, Trash2
} from "lucide-react";
import { listJobs, approveJob, rejectJob, archiveJob, unarchiveJob, deleteJob } from "../services/api";
import { useToast } from "../components/Toast";
import { SkeletonCard } from "../components/Skeleton";

const API_BASE = import.meta.env.VITE_API_URL?.replace("/api/v1", "") || "http://localhost:8002";

const VIEW_LABELS = {
  frente: "Frente", costas: "Costas",
  lat_direita: "Lat. D", lat_esquerda: "Lat. E"
};

const COLOR_NAMES = {
  "#696980": "Grafite",
  "#978b7b": "Areia",
  "#9e987d": "Musgo",
  "#ffffff": "Branco",
  "#000000": "Preto",
  "#ff0000": "Vermelho",
  "#0000ff": "Azul",
  "#008000": "Verde",
};

const getColorName = (hex) =>
  COLOR_NAMES[hex?.toLowerCase()] ?? null;

const buildFilename = (job) => {
  const color = (job.result?.color_hex || "#000").replace("#", "").toLowerCase();
  const view = job.view || "img";
  const viewLabel = { frente: "frente", costas: "costas", lat_direita: "lat-d", lat_esquerda: "lat-e" }[view] || view;
  const hash = job.id.slice(0, 6);
  return `confexai_${color}_${viewLabel}_${hash}.jpg`;
};

export default function Resultados() {
  const navigate = useNavigate();
  const { toast } = useToast();

  const [jobsByProduct, setJobsByProduct] = useState({});
  const [expanded, setExpanded] = useState({});
  const [selected, setSelected] = useState(new Set());       // product IDs
  const [selectedImages, setSelectedImages] = useState(new Set()); // individual job IDs
  const [loading, setLoading] = useState(true);
  const [showArchived, setShowArchived] = useState(false);
  const [seoReadyProductIds, setSeoReadyProductIds] = useState(new Set());

  const load = async () => {
    setLoading(true);
    try {
      const [res, seoRes] = await Promise.all([
        listJobs(null, "color_variation", null, showArchived),
        listJobs(null, "seo_description", "done").catch(() => ({ data: { data: [] } })),
      ]);
      const jobs = res.data.data;

      // Build SEO-ready product IDs set
      const seoIds = new Set(
        (seoRes?.data?.data ?? []).map((j) => j.product_id).filter(Boolean)
      );
      setSeoReadyProductIds(seoIds);

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

  const handleArchiveJob = async (jobId, productId) => {
    try {
      await archiveJob(jobId);
      setJobsByProduct((prev) => ({
        ...prev,
        [productId]: {
          ...prev[productId],
          jobs: prev[productId].jobs.filter((j) => j.id !== jobId),
        },
      }));
      toast("Job arquivado", "info");
    } catch { toast("Erro ao arquivar job", "error"); }
  };

  const handleUnarchiveJob = async (jobId, productId) => {
    try {
      await unarchiveJob(jobId);
      setJobsByProduct((prev) => ({
        ...prev,
        [productId]: {
          ...prev[productId],
          jobs: prev[productId].jobs.filter((j) => j.id !== jobId),
        },
      }));
      toast("Job desarquivado", "success");
    } catch { toast("Erro ao desarquivar job", "error"); }
  };

  const handleDeleteJob = async (jobId, productId) => {
    if (!window.confirm("Remover esta imagem da visualização permanentemente?")) return;
    try {
      await deleteJob(jobId);
      setJobsByProduct((prev) => {
        const updated = { ...prev };
        if (updated[productId]) {
          updated[productId] = {
            ...updated[productId],
            jobs: updated[productId].jobs.filter((j) => j.id !== jobId),
          };
        }
        return updated;
      });
      toast("Imagem removida da visualização", "success");
    } catch (err) {
      toast(err.response?.data?.detail || "Erro ao remover", "error");
    }
  };

  const downloadProduct = (productId) => {
    const url = `${API_BASE}/api/v1/jobs/export/${productId}`;
    const token = localStorage.getItem("confexai_token");
    fetch(url, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.blob())
      .then((blob) => {
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = `produto_${productId}.zip`;
        a.click();
        URL.revokeObjectURL(a.href);
      })
      .catch(() => toast("Erro ao baixar", "error"));
  };

  const downloadImage = (jpgUrl, filename) => {
    const fullUrl = `${API_BASE}${jpgUrl}`;
    const a = document.createElement("a");
    a.href = fullUrl;
    a.download = filename || "imagem.jpg";
    a.target = "_blank";
    a.click();
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
      .catch(() => toast("Erro ao baixar selecao", "error"));
  };

  const toggleSelect = (productId) => {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(productId) ? next.delete(productId) : next.add(productId);
      return next;
    });
  };

  const toggleImage = (jobId) => {
    setSelectedImages((prev) => {
      const next = new Set(prev);
      next.has(jobId) ? next.delete(jobId) : next.add(jobId);
      return next;
    });
  };

  const downloadSelectedImages = () => {
    if (selectedImages.size === 0) return;
    let delay = 0;
    for (const jobId of selectedImages) {
      for (const { jobs } of Object.values(jobsByProduct)) {
        const job = jobs.find(j => j.id === jobId);
        if (job?.result?.jpg_url) {
          setTimeout(() => {
            const a = document.createElement("a");
            a.href = `${API_BASE}${job.result.jpg_url}`;
            a.download = buildFilename(job);
            a.click();
          }, delay);
          delay += 300;
          break;
        }
      }
    }
    setSelectedImages(new Set());
  };

  const selectAllInProduct = (productId) => {
    const jobIds = (jobsByProduct[productId]?.jobs ?? []).map((j) => j.id);
    setSelectedImages((prev) => {
      const next = new Set(prev);
      const allSelected = jobIds.every((id) => next.has(id));
      if (allSelected) {
        jobIds.forEach((id) => next.delete(id));
      } else {
        jobIds.forEach((id) => next.add(id));
      }
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
            {productList.length} produtos · {totalJobs} variacoes geradas
          </p>
        </div>
        <div className="flex items-center gap-3">
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

          {selected.size > 0 && (
            <button
              onClick={downloadBulk}
              className="flex items-center gap-2 px-4 py-2 bg-amber-500 hover:bg-amber-400 text-surface-950 rounded-md text-sm font-medium transition-colors"
            >
              <Download size={14} />
              Baixar selecao ({selected.size})
            </button>
          )}

          {selectedImages.size > 0 && (
            <button
              onClick={downloadSelectedImages}
              className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-md text-sm font-medium transition-colors"
            >
              <Download size={14} />
              Baixar {selectedImages.size} {selectedImages.size === 1 ? "imagem" : "imagens"}
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
        <div className="grid grid-cols-4 gap-3">
          {[1,2,3,4,5,6,7,8].map((i) => (
            <SkeletonCard key={i} />
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
                        {jobs.length} variacoes ·{" "}
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

                  <div className="flex items-center gap-2 shrink-0">
                    <button
                      onClick={() => selectAllInProduct(productId)}
                      className="text-xs text-amber-400 hover:text-amber-300 underline underline-offset-2 transition-colors"
                    >
                      selecionar grupo
                    </button>
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
                          const colorName = getColorName(colorHex);
                          const viewLabel = VIEW_LABELS[job.view] || job.view || "";
                          const filename = buildFilename(job);
                          const isJobSelected = selectedImages.has(job.id);

                          return (
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
                                  <img src={fullUrl} alt={colorName || colorHex} className="w-full h-full object-contain" />
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

                                {/* Quality warning badge */}
                                {result?.quality_metrics?.quality_warning && (
                                  <span className="absolute top-2 left-20 text-xs bg-amber-500/20 text-amber-400 px-1.5 py-0.5 rounded font-mono z-10">
                                    Qualidade baixa
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
                                    className="w-3.5 h-3.5 rounded border border-white/20 shrink-0"
                                    style={{ backgroundColor: colorHex }}
                                  />
                                  <span className="text-xs font-mono text-neutral-400">{colorHex}</span>
                                  {colorName && (
                                    <span className="text-xs text-neutral-500">· {colorName}</span>
                                  )}
                                </div>
                                <p className="text-[10px] font-mono text-neutral-600 mt-0.5">
                                  #{String(job.id).slice(0, 8)}
                                </p>

                                {job.status === "pending_review" && (
                                  <div className="flex gap-1 mt-1.5">
                                    <button
                                      onClick={() => handleApprove(job.id, productId)}
                                      className="flex-1 flex items-center justify-center gap-1 py-1 bg-amber-500 hover:bg-amber-400 text-surface-950 rounded text-xs font-medium transition-colors"
                                    >
                                      <Check size={10} /> Aprovar
                                    </button>
                                    <button
                                      onClick={() => handleReject(job.id, productId)}
                                      className="flex-1 flex items-center justify-center gap-1 py-1 bg-red-950/40 hover:bg-red-900/60 border border-red-800/40 text-red-400 hover:text-red-300 rounded text-xs transition-colors"
                                    >
                                      <X size={10} /> Rejeitar
                                    </button>
                                  </div>
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
