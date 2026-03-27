import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Sparkles, Copy, Check, AlertTriangle, ArrowLeft, RefreshCw } from "lucide-react";
import { generateSEO, getSEO, getProduct } from "../services/api";
import { useToast } from "../components/Toast";

const PLATFORMS = [
  { key: "mercadolivre", label: "Mercado Livre", color: "text-yellow-400", limit: 60 },
  { key: "shopee", label: "Shopee", color: "text-orange-400", limit: 120 },
  { key: "shopify", label: "Shopify", color: "text-green-400", limit: 70 },
];

const DEFAULT_COLORS = ["#696980", "#978b7b", "#9e987d"];

export default function SEO() {
  const { productId } = useParams();
  const navigate = useNavigate();
  const { toast } = useToast();

  const [product, setProduct] = useState(null);
  const [descriptions, setDescriptions] = useState([]);
  const [generating, setGenerating] = useState(false);
  const [selectedPlatforms, setSelectedPlatforms] = useState(["mercadolivre", "shopee", "shopify"]);
  const [colors, setColors] = useState(DEFAULT_COLORS);
  const [analysis, setAnalysis] = useState(null);
  const [copied, setCopied] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      getProduct(productId),
      getSEO(productId),
    ]).then(([prodRes, seoRes]) => {
      setProduct(prodRes.data.data);
      setDescriptions(seoRes.data.data);
    }).catch(() => toast("Erro ao carregar produto", "error"))
      .finally(() => setLoading(false));
  }, [productId]);

  const handleGenerate = async () => {
    if (selectedPlatforms.length === 0) {
      toast("Selecione ao menos uma plataforma", "warning");
      return;
    }
    setGenerating(true);
    try {
      const res = await generateSEO(productId, selectedPlatforms, colors);
      const data = res.data.data;
      setAnalysis(data.garment_analysis);

      // Recarregar descrições do banco
      const seoRes = await getSEO(productId);
      setDescriptions(seoRes.data.data);

      const totalCost = data.total_cost_cents;
      toast(
        `${selectedPlatforms.length} descrições geradas — ${totalCost}¢ (R$${(totalCost * 0.006).toFixed(2)})`,
        "success"
      );

      // Avisar sobre warnings
      const withWarnings = data.results.filter(r => r.warnings?.length > 0);
      if (withWarnings.length > 0) {
        toast(`${withWarnings.length} plataforma(s) com avisos — verifique os títulos`, "warning");
      }
    } catch (err) {
      toast(err.response?.data?.detail || "Erro ao gerar SEO", "error");
    } finally {
      setGenerating(false);
    }
  };

  const copyToClipboard = async (text, key) => {
    await navigator.clipboard.writeText(text);
    setCopied(key);
    setTimeout(() => setCopied(null), 2000);
  };

  const togglePlatform = (key) => {
    setSelectedPlatforms(prev =>
      prev.includes(key) ? prev.filter(p => p !== key) : [...prev, key]
    );
  };

  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-center gap-4 mb-8">
        <button onClick={() => navigate("/produtos")} className="text-neutral-500 hover:text-neutral-300">
          <ArrowLeft size={18} />
        </button>
        <div className="flex-1">
          <p className="text-xs text-neutral-500 uppercase tracking-wider mb-0.5">Descrições SEO</p>
          <h1 className="font-display text-2xl text-neutral-100">
            {product?.name || "Carregando..."}
          </h1>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-6">
        {/* Coluna esquerda — configuração */}
        <div className="space-y-4">
          {/* Seleção de plataformas */}
          <div className="bg-surface-800 border border-surface-600 rounded-xl p-4">
            <p className="text-xs text-neutral-500 uppercase tracking-wider mb-3">Plataformas</p>
            <div className="space-y-2">
              {PLATFORMS.map(({ key, label, color }) => (
                <button
                  key={key}
                  onClick={() => togglePlatform(key)}
                  className={`w-full flex items-center justify-between px-3 py-2 rounded-lg border transition-all text-sm ${
                    selectedPlatforms.includes(key)
                      ? "border-amber-500/40 bg-amber-500/5 text-neutral-100"
                      : "border-surface-600 bg-surface-700 text-neutral-400"
                  }`}
                >
                  <span className={selectedPlatforms.includes(key) ? color : ""}>{label}</span>
                  {selectedPlatforms.includes(key) && <Check size={14} className="text-amber-400" />}
                </button>
              ))}
            </div>
          </div>

          {/* Análise da peça */}
          {analysis && (
            <div className="bg-surface-800 border border-surface-600 rounded-xl p-4">
              <p className="text-xs text-neutral-500 uppercase tracking-wider mb-3">Análise da peça</p>
              <div className="space-y-1.5 text-xs">
                {[
                  ["Tipo", analysis.garment_type],
                  ["Público", analysis.gender_target],
                  ["Modelagem", analysis.modeling],
                  ["Tecido", analysis.fabric_apparent],
                  ["Estilo", analysis.style],
                  ["Estação", analysis.season],
                  ["Lavagem", analysis.wash_care_likely],
                ].map(([label, value]) => value && (
                  <div key={label} className="flex justify-between">
                    <span className="text-neutral-500">{label}</span>
                    <span className="text-neutral-300 text-right max-w-32 truncate">{value}</span>
                  </div>
                ))}
                {analysis.notable_details?.length > 0 && (
                  <div>
                    <span className="text-neutral-500">Detalhes</span>
                    <p className="text-neutral-300 mt-0.5">{analysis.notable_details.join(", ")}</p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Botão gerar */}
          <button
            onClick={handleGenerate}
            disabled={generating || selectedPlatforms.length === 0}
            className="w-full flex items-center justify-center gap-2 py-3 bg-amber-500 hover:bg-amber-400 disabled:opacity-40 disabled:cursor-not-allowed text-surface-950 rounded-xl font-medium transition-colors"
          >
            {generating ? (
              <><RefreshCw size={16} className="animate-spin" /> Gerando...</>
            ) : (
              <><Sparkles size={16} /> Gerar SEO</>
            )}
          </button>
        </div>

        {/* Coluna direita — resultados */}
        <div className="col-span-2 space-y-4">
          {loading ? (
            <div className="space-y-3">
              {[1, 2, 3].map(i => (
                <div key={i} className="bg-surface-800 border border-surface-700 rounded-xl h-40 animate-pulse" />
              ))}
            </div>
          ) : descriptions.length === 0 ? (
            <div className="text-center py-20 text-neutral-600">
              <Sparkles size={40} className="mx-auto mb-3 opacity-30" />
              <p className="text-sm">Nenhuma descrição gerada ainda</p>
              <p className="text-xs mt-1">Selecione as plataformas e clique em Gerar SEO</p>
            </div>
          ) : (
            PLATFORMS.filter(p => descriptions.find(d => d.platform === p.key)).map(({ key, label, color, limit }) => {
              const desc = descriptions.find(d => d.platform === key);
              if (!desc) return null;

              const titleOver = desc.title_char_count > limit;
              const tags = Array.isArray(desc.tags) ? desc.tags : [];

              return (
                <div key={key} className="bg-surface-800 border border-surface-600 rounded-xl p-5">
                  {/* Platform header */}
                  <div className="flex items-center justify-between mb-4">
                    <span className={`text-sm font-medium ${color}`}>{label}</span>
                    <span className="text-xs text-neutral-600">
                      {new Date(desc.created_at).toLocaleString("pt-BR")}
                    </span>
                  </div>

                  {/* Título */}
                  <div className="mb-3">
                    <div className="flex items-center justify-between mb-1">
                      <p className="text-xs text-neutral-500">Título</p>
                      <div className="flex items-center gap-2">
                        {titleOver && <AlertTriangle size={12} className="text-red-400" />}
                        <span className={`text-xs font-mono ${titleOver ? "text-red-400" : "text-neutral-500"}`}>
                          {desc.title_char_count}/{limit}
                        </span>
                        <button
                          onClick={() => copyToClipboard(desc.title, `${key}-title`)}
                          className="text-neutral-600 hover:text-amber-400 transition-colors"
                        >
                          {copied === `${key}-title` ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} />}
                        </button>
                      </div>
                    </div>
                    <p className="text-sm text-neutral-100 bg-surface-700 rounded px-3 py-2">
                      {desc.title}
                    </p>
                  </div>

                  {/* Descrição */}
                  <div className="mb-3">
                    <div className="flex items-center justify-between mb-1">
                      <p className="text-xs text-neutral-500">Descrição</p>
                      <button
                        onClick={() => copyToClipboard(desc.description, `${key}-desc`)}
                        className="text-neutral-600 hover:text-amber-400 transition-colors"
                      >
                        {copied === `${key}-desc` ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} />}
                      </button>
                    </div>
                    <div
                      className="text-sm text-neutral-300 bg-surface-700 rounded px-3 py-2 max-h-32 overflow-auto whitespace-pre-wrap"
                      dangerouslySetInnerHTML={{ __html: desc.description }}
                    />
                  </div>

                  {/* Tags */}
                  {tags.length > 0 && (
                    <div>
                      <div className="flex items-center justify-between mb-1">
                        <p className="text-xs text-neutral-500">Tags ({tags.length})</p>
                        <button
                          onClick={() => copyToClipboard(tags.join(", "), `${key}-tags`)}
                          className="text-neutral-600 hover:text-amber-400 transition-colors"
                        >
                          {copied === `${key}-tags` ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} />}
                        </button>
                      </div>
                      <div className="flex flex-wrap gap-1">
                        {tags.map((tag, i) => (
                          <span key={i} className="text-xs bg-surface-700 text-neutral-400 px-2 py-0.5 rounded">
                            {tag}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
