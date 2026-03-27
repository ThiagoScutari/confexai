import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Sparkles, Copy, Check, AlertTriangle, ArrowLeft, RefreshCw } from "lucide-react";
import { generateSEO, getSEO, getProduct, listJobs } from "../services/api";
import { useToast } from "../components/Toast";

const ML_FIELDS = [
  {
    key: "title",
    label: "Titulo do Anuncio",
    mlField: "Titulo",
    limit: 60,
    help: "Campo principal de busca no ML. Aparece nos resultados de pesquisa.",
    format: "Tipo + Feature + Genero - Ex: Blusa Feminina Floral Viscose - P ao GG",
  },
  {
    key: "description",
    label: "Descricao do Produto",
    mlField: "Descricao",
    limit: 4000,
    help: "Texto completo da pagina do produto. Suporta paragrafos.",
  },
  {
    key: "tags",
    label: "Palavras-chave",
    mlField: "Palavras-chave do anuncio",
    limit: null,
    help: "Ate 5 termos de busca adicionais indexados pelo ML.",
  },
];

export default function SEO() {
  const { productId } = useParams();
  const navigate = useNavigate();
  const { toast } = useToast();

  const [product, setProduct] = useState(null);
  const [mlResult, setMlResult] = useState(null);
  const [generating, setGenerating] = useState(false);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(null);

  // Operator context fields
  const [fabric, setFabric] = useState("");
  const [genderTarget, setGenderTarget] = useState("");
  const [sizingInfo, setSizingInfo] = useState("");
  const [additionalNotes, setAdditionalNotes] = useState("");

  // Real colors from approved jobs
  const [realColors, setRealColors] = useState([]);

  // Garment analysis from AI
  const [analysis, setAnalysis] = useState(null);

  useEffect(() => {
    Promise.all([
      getProduct(productId),
      getSEO(productId),
      listJobs(productId, "color_variation", "approved").catch(() => ({ data: { data: [] } })),
    ]).then(([prodRes, seoRes, jobsRes]) => {
      setProduct(prodRes.data.data);

      // Load existing ML description
      const descs = seoRes.data.data;
      const ml = descs.find((d) => d.platform === "mercadolivre");
      if (ml) {
        setMlResult({
          title: ml.title,
          description: ml.description,
          tags: Array.isArray(ml.tags) ? ml.tags : [],
          title_char_count: ml.title_char_count,
        });
      }

      // Extract real colors from approved jobs
      const jobs = jobsRes?.data?.data ?? [];
      const colors = [...new Set(
        jobs
          .map((j) => j.result?.color_hex)
          .filter(Boolean)
      )];
      setRealColors(colors);
    }).catch(() => toast("Erro ao carregar produto", "error"))
      .finally(() => setLoading(false));
  }, [productId]);

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      const payload = {
        platforms: ["mercadolivre"],
        colors: realColors,
        image_id: null,
        fabric: fabric || null,
        gender_target: genderTarget || null,
        sizing_info: sizingInfo || null,
        additional_notes: additionalNotes || null,
      };
      const res = await generateSEO(productId, payload);
      const data = res.data.data;
      setAnalysis(data.garment_analysis);

      const totalCost = data.total_cost_cents;
      toast(
        `Descricao gerada — ${totalCost}c (R$${(totalCost * 0.006).toFixed(2)})`,
        "success"
      );

      if (data.results?.[0]?.warnings?.length > 0) {
        toast("Avisos detectados — verifique o titulo", "warning");
      }

      // Reload from DB
      const seoRes = await getSEO(productId);
      const ml = seoRes.data.data.find((d) => d.platform === "mercadolivre");
      if (ml) {
        setMlResult({
          title: ml.title,
          description: ml.description,
          tags: Array.isArray(ml.tags) ? ml.tags : [],
          title_char_count: ml.title_char_count,
        });
      }
    } catch (err) {
      toast(err.response?.data?.detail || "Erro ao gerar SEO", "error");
    } finally {
      setGenerating(false);
    }
  };

  const copyText = (text, key) => {
    navigator.clipboard.writeText(text);
    setCopied(key);
    setTimeout(() => setCopied(null), 2000);
  };

  if (loading) {
    return (
      <div className="p-8 space-y-4">
        <div className="h-8 w-64 bg-surface-700 rounded animate-pulse" />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-20 bg-surface-800 border border-surface-700 rounded-xl animate-pulse" />
            ))}
          </div>
          <div className="h-64 bg-surface-800 border border-surface-700 rounded-xl animate-pulse" />
        </div>
      </div>
    );
  }

  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-center gap-4 mb-8">
        <button onClick={() => navigate("/produtos")} className="text-neutral-500 hover:text-neutral-300">
          <ArrowLeft size={18} />
        </button>
        <div className="flex-1">
          <p className="text-xs text-neutral-500 uppercase tracking-wider mb-0.5">SEO — Mercado Livre</p>
          <h1 className="font-display text-2xl text-neutral-100">
            {product?.name || "Carregando..."}
          </h1>
        </div>
        <span className="text-xs bg-amber-500/10 border border-amber-500/30 text-amber-400 px-2 py-1 rounded font-mono">
          Mercado Livre
        </span>
        <span className="text-xs text-neutral-500">Shopee e Shopify em breve</span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* LEFT — Context form + generate */}
        <div className="space-y-4">
          <div className="bg-surface-800 border border-surface-600 rounded-xl p-5 space-y-4">
            <div>
              <p className="text-xs font-medium text-neutral-300 uppercase tracking-wider mb-0.5">Contexto do produto</p>
              <p className="text-[11px] text-neutral-600">Quanto mais voce informar, melhor o resultado gerado.</p>
            </div>

            {/* Tecido */}
            <div className="space-y-1">
              <label className="text-xs font-medium text-neutral-400 uppercase tracking-wider">
                Tecido / Composicao
              </label>
              <input
                type="text"
                value={fabric}
                onChange={(e) => setFabric(e.target.value)}
                placeholder="ex: 100% algodao, viscose, linho..."
                className="w-full bg-surface-700 border border-surface-600 rounded-lg px-3 py-2 text-sm text-neutral-100 placeholder-neutral-600 focus:outline-none focus:border-amber-500/50"
              />
              <p className="text-[11px] text-neutral-600">
                Ajuda na inferencia de cuidados de lavagem e posicionamento
              </p>
            </div>

            {/* Publico-alvo */}
            <div className="space-y-1">
              <label className="text-xs font-medium text-neutral-400 uppercase tracking-wider">
                Publico-alvo
              </label>
              <div className="flex gap-2 flex-wrap">
                {["Feminino", "Masculino", "Unissex", "Infantil"].map((g) => (
                  <button
                    key={g}
                    type="button"
                    onClick={() => setGenderTarget(
                      genderTarget === g.toLowerCase() ? "" : g.toLowerCase()
                    )}
                    className={`px-3 py-1.5 rounded-lg text-xs border transition-all ${
                      genderTarget === g.toLowerCase()
                        ? "bg-amber-500/20 border-amber-500/50 text-amber-400"
                        : "bg-surface-700 border-surface-600 text-neutral-400 hover:border-surface-500"
                    }`}
                  >
                    {g}
                  </button>
                ))}
              </div>
            </div>

            {/* Grade de tamanhos */}
            <div className="space-y-1">
              <label className="text-xs font-medium text-neutral-400 uppercase tracking-wider">
                Grade de Tamanhos
              </label>
              <input
                type="text"
                value={sizingInfo}
                onChange={(e) => setSizingInfo(e.target.value)}
                placeholder="ex: P ao GG, 36 ao 46, tamanho unico..."
                className="w-full bg-surface-700 border border-surface-600 rounded-lg px-3 py-2 text-sm text-neutral-100 placeholder-neutral-600 focus:outline-none focus:border-amber-500/50"
              />
            </div>

            {/* Observacoes */}
            <div className="space-y-1">
              <label className="text-xs font-medium text-neutral-400 uppercase tracking-wider">
                Observacoes do Operador
              </label>
              <textarea
                value={additionalNotes}
                onChange={(e) => setAdditionalNotes(e.target.value)}
                rows={3}
                placeholder="ex: tem forro, botoes dourados, colecao verao 2026..."
                className="w-full bg-surface-700 border border-surface-600 rounded-lg px-3 py-2 text-sm text-neutral-100 placeholder-neutral-600 focus:outline-none focus:border-amber-500/50 resize-none"
              />
              <p className="text-[11px] text-neutral-600">
                Detalhes que a camera pode nao capturar
              </p>
            </div>
          </div>

          {/* Real colors detected */}
          {realColors.length > 0 && (
            <div className="bg-surface-800 border border-surface-600 rounded-xl p-4">
              <p className="text-xs text-neutral-500 uppercase tracking-wider mb-2">Cores aprovadas</p>
              <div className="flex gap-2 flex-wrap">
                {realColors.map((c) => (
                  <div key={c} className="flex items-center gap-1.5 bg-surface-700 border border-surface-600 rounded px-2 py-1">
                    <div className="w-3 h-3 rounded-full border border-surface-500" style={{ backgroundColor: c }} />
                    <span className="text-xs font-mono text-neutral-400">{c}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Garment analysis */}
          {analysis && (
            <div className="bg-surface-800 border border-surface-600 rounded-xl p-4">
              <p className="text-xs text-neutral-500 uppercase tracking-wider mb-3">Analise da peca (AI)</p>
              <div className="space-y-1.5 text-xs">
                {[
                  ["Tipo", analysis.garment_type],
                  ["Publico", analysis.gender_target],
                  ["Modelagem", analysis.modeling],
                  ["Tecido", analysis.fabric_apparent],
                  ["Estilo", analysis.style],
                  ["Estacao", analysis.season],
                  ["Lavagem", analysis.wash_care_likely],
                ].map(([label, value]) => value && (
                  <div key={label} className="flex justify-between">
                    <span className="text-neutral-500">{label}</span>
                    <span className="text-neutral-300 text-right max-w-32 truncate">{value}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Generate button */}
          <button
            onClick={handleGenerate}
            disabled={generating}
            className="w-full flex items-center justify-center gap-2 py-3 bg-amber-500 hover:bg-amber-400 disabled:opacity-40 disabled:cursor-not-allowed text-surface-950 rounded-xl font-medium transition-colors"
          >
            {generating ? (
              <><RefreshCw size={16} className="animate-spin" /> Gerando...</>
            ) : (
              <><Sparkles size={16} /> Gerar descricao para Mercado Livre</>
            )}
          </button>
          <p className="text-[11px] text-neutral-600 text-center">
            ~6c por geracao — apenas Mercado Livre
          </p>
        </div>

        {/* RIGHT — ML results read-only */}
        <div className="space-y-4">
          {!mlResult ? (
            <div className="text-center py-20 text-neutral-600">
              <Sparkles size={40} className="mx-auto mb-3 opacity-30" />
              <p className="text-sm">Nenhuma descricao gerada ainda</p>
              <p className="text-xs mt-1">Preencha o contexto e clique em Gerar</p>
            </div>
          ) : (
            ML_FIELDS.map((field) => {
              const value = mlResult?.[field.key];
              if (!value) return null;
              const isArray = Array.isArray(value);
              const charCount = isArray ? value.length : (value?.length ?? 0);

              return (
                <div key={field.key} className="bg-surface-800 border border-surface-600 rounded-xl p-5 space-y-2">
                  {/* Header */}
                  <div className="flex items-start justify-between">
                    <div className="space-y-0.5">
                      <span className="text-xs font-medium text-neutral-300">
                        {field.label}
                      </span>
                      <span className="ml-2 text-[10px] font-mono text-neutral-600 bg-surface-700 px-1.5 py-0.5 rounded border border-surface-600">
                        ML &rsaquo; {field.mlField}
                      </span>
                    </div>
                    <button
                      type="button"
                      onClick={() => {
                        const text = isArray ? value.join(", ") : value;
                        copyText(text, field.key);
                      }}
                      className="text-neutral-600 hover:text-amber-400 transition-colors"
                      title="Copiar"
                    >
                      {copied === field.key ? <Check size={13} className="text-emerald-400" /> : <Copy size={13} />}
                    </button>
                  </div>

                  {/* Help text */}
                  <p className="text-[11px] text-neutral-600">{field.help}</p>
                  {field.format && (
                    <p className="text-[11px] text-neutral-600 italic">Formato: {field.format}</p>
                  )}

                  {/* Content — READ ONLY */}
                  {isArray ? (
                    <div className="flex flex-wrap gap-1.5">
                      {value.map((tag, i) => (
                        <span key={i} className="text-xs bg-surface-700 border border-surface-600 text-neutral-300 px-2 py-1 rounded-full font-mono">
                          {tag}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <div className="bg-surface-700 border border-surface-600 rounded-lg p-3">
                      <p className="text-sm text-neutral-100 whitespace-pre-wrap leading-relaxed select-text">
                        {value}
                      </p>
                    </div>
                  )}

                  {/* Character counter with progress bar */}
                  {field.limit && (
                    <div className="space-y-1">
                      <div className="flex justify-between text-[10px] font-mono">
                        <span className={charCount > field.limit ? "text-red-400" : "text-neutral-600"}>
                          {charCount} / {field.limit} chars
                        </span>
                        {charCount > field.limit && (
                          <span className="text-red-400">
                            {charCount - field.limit} acima do limite
                          </span>
                        )}
                      </div>
                      <div className="h-1 bg-surface-600 rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all ${
                            charCount > field.limit ? "bg-red-500" : "bg-amber-500"
                          }`}
                          style={{
                            width: `${Math.min((charCount / field.limit) * 100, 100)}%`,
                          }}
                        />
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
