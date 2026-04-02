import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  ArrowLeft, Package, Images, Sparkles, Clock, Copy, Check,
  ChevronRight, Download
} from "lucide-react";
import { getProductSummary } from "../services/api";
import { useToast } from "../components/Toast";
import { SkeletonCard } from "../components/Skeleton";

const API_BASE = import.meta.env.VITE_API_URL?.replace("/api/v1", "") || "http://localhost:8002";

const TABS = [
  { id: "overview", label: "Visão Geral", icon: Package },
  { id: "variations", label: "Variações", icon: Images },
  { id: "seo", label: "SEO", icon: Sparkles },
  { id: "history", label: "Histórico", icon: Clock },
];

const VIEW_LABELS = {
  frente: "Frente", costas: "Costas",
  lat_direita: "Lat. Direita", lat_esquerda: "Lat. Esquerda",
};
const ALL_VIEWS = ["frente", "costas", "lat_direita", "lat_esquerda"];

export default function Produto() {
  const { productId } = useParams();
  const navigate = useNavigate();
  const { toast } = useToast();

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState("overview");
  const [copied, setCopied] = useState(null);

  useEffect(() => {
    getProductSummary(productId)
      .then((r) => setData(r.data.data))
      .catch(() => toast("Erro ao carregar produto", "error"))
      .finally(() => setLoading(false));
  }, [productId]);

  const copyText = (text, key) => {
    navigator.clipboard.writeText(text);
    setCopied(key);
    setTimeout(() => setCopied(null), 2000);
  };

  if (loading) {
    return (
      <div className="p-8 space-y-6">
        <div className="h-8 w-64 bg-surface-700 rounded animate-pulse" />
        <div className="grid grid-cols-4 gap-3">
          {[1,2,3,4].map(i => <SkeletonCard key={i} />)}
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="p-8 text-center py-24 text-neutral-600">
        <Package size={40} className="mx-auto mb-3 opacity-30" />
        <p className="text-sm">Produto não encontrado</p>
        <button onClick={() => navigate("/produtos")} className="mt-4 text-sm text-amber-400 hover:text-amber-300">
          Voltar para produtos
        </button>
      </div>
    );
  }

  const { product, images, approved_variations, seo, stats } = data;
  const imagesByView = {};
  images.forEach((img) => { imagesByView[img.view] = img; });

  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-center gap-4 mb-6">
        <button onClick={() => navigate("/produtos")} className="text-neutral-500 hover:text-neutral-300">
          <ArrowLeft size={18} />
        </button>
        <div className="flex-1">
          <h1 className="font-display text-2xl text-neutral-100">{product.name}</h1>
          <p className="text-sm text-neutral-500 mt-0.5">{product.category} · {product.fabric}</p>
        </div>
        <button
          onClick={() => navigate(`/pipeline/${productId}`)}
          className="px-4 py-2 bg-amber-500 hover:bg-amber-400 text-surface-950 text-sm font-medium rounded-lg transition-colors"
        >
          Executar Pipeline
        </button>
      </div>

      {/* Stats bar */}
      <div className="grid grid-cols-4 gap-3 mb-6">
        {[
          { label: "Views enviadas", value: stats.views_uploaded, max: 4 },
          { label: "Variações aprovadas", value: stats.variations_approved },
          { label: "Plataformas SEO", value: stats.platforms_with_seo },
          { label: "Custo total", value: `R$ ${stats.total_cost_brl.toFixed(2)}` },
        ].map(({ label, value, max }) => (
          <div key={label} className="bg-surface-800 border border-surface-700 rounded-xl p-4">
            <p className="text-xs text-neutral-500 mb-1">{label}</p>
            <p className="text-lg font-medium text-neutral-100">
              {value}{max ? <span className="text-neutral-600 text-sm font-normal">/{max}</span> : null}
            </p>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 border-b border-surface-700 pb-px">
        {TABS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={`flex items-center gap-2 px-4 py-2.5 text-sm rounded-t-lg transition-colors ${
              tab === id
                ? "bg-surface-800 text-amber-400 border-b-2 border-amber-500"
                : "text-neutral-500 hover:text-neutral-300 hover:bg-surface-800/50"
            }`}
          >
            <Icon size={14} />
            {label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {tab === "overview" && <OverviewTab images={imagesByView} product={product} />}
      {tab === "variations" && <VariationsTab variations={approved_variations} navigate={navigate} productId={productId} />}
      {tab === "seo" && <SEOTab seo={seo} copied={copied} copyText={copyText} navigate={navigate} productId={productId} />}
      {tab === "history" && <HistoryTab stats={stats} navigate={navigate} productId={productId} />}
    </div>
  );
}

function OverviewTab({ images, product }) {
  return (
    <div className="grid grid-cols-2 gap-6">
      <div>
        <p className="text-xs text-neutral-500 uppercase tracking-wider mb-3">Views da peça</p>
        <div className="grid grid-cols-2 gap-3">
          {ALL_VIEWS.map((view) => {
            const img = images[view];
            return (
              <div key={view} className="bg-surface-800 border border-surface-700 rounded-xl overflow-hidden">
                <div className="aspect-square bg-surface-900 flex items-center justify-center">
                  {img?.public_url ? (
                    <img src={`${API_BASE}${img.public_url}`} alt={view} className="w-full h-full object-contain" />
                  ) : (
                    <div className="text-center">
                      <Images size={20} className="mx-auto mb-1 text-neutral-700" />
                      <p className="text-xs text-neutral-600">Não enviada</p>
                    </div>
                  )}
                </div>
                <div className="p-2.5 border-t border-surface-700">
                  <p className="text-xs font-medium text-neutral-300">{VIEW_LABELS[view]}</p>
                  <p className="text-[10px] text-neutral-600 font-mono">{img ? "Enviada" : "Pendente"}</p>
                </div>
              </div>
            );
          })}
        </div>
      </div>
      <div>
        <p className="text-xs text-neutral-500 uppercase tracking-wider mb-3">Dados do produto</p>
        <div className="bg-surface-800 border border-surface-700 rounded-xl p-5 space-y-3">
          {[
            ["Nome", product.name],
            ["Categoria", product.category],
            ["Tecido", product.fabric],
            ["Observações", product.notes || "—"],
            ["Criado em", new Date(product.created_at).toLocaleDateString("pt-BR")],
          ].map(([label, value]) => (
            <div key={label} className="flex justify-between">
              <span className="text-xs text-neutral-500">{label}</span>
              <span className="text-xs text-neutral-200 text-right max-w-48 truncate">{value}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function VariationsTab({ variations, navigate, productId }) {
  if (variations.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-24 text-center">
        <div className="w-16 h-16 rounded-2xl bg-surface-800 border border-surface-700 flex items-center justify-center mb-4">
          <Images size={28} className="text-neutral-600" />
        </div>
        <h3 className="font-display text-lg text-neutral-300 mb-2">Nenhuma variação aprovada</h3>
        <p className="text-sm text-neutral-500 max-w-xs mb-6">
          Execute o pipeline e aprove as variações de cor para vê-las aqui.
        </p>
        <button onClick={() => navigate(`/pipeline/${productId}`)}
          className="px-4 py-2 bg-amber-500 hover:bg-amber-400 text-surface-950 text-sm font-medium rounded-lg transition-colors">
          Executar Pipeline
        </button>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-4 gap-3">
      {variations.map((v) => (
        <div key={v.id} className="bg-surface-800 border border-surface-700 rounded-xl overflow-hidden group">
          <div className="relative aspect-square bg-surface-900">
            {v.jpg_url ? (
              <img src={`${API_BASE}${v.jpg_url}`} alt={v.color_hex} className="w-full h-full object-contain" />
            ) : (
              <div className="w-full h-full flex items-center justify-center">
                <div className="w-12 h-12 rounded-full border border-white/10" style={{ backgroundColor: v.color_hex || "#888" }} />
              </div>
            )}
            {v.view && (
              <span className="absolute top-2 left-2 text-xs bg-black/70 text-white px-1.5 py-0.5 rounded font-mono">
                {VIEW_LABELS[v.view] || v.view}
              </span>
            )}
            <span className="absolute bottom-2 right-2 flex items-center gap-0.5 text-xs bg-emerald-500/20 text-emerald-400 px-1.5 py-0.5 rounded font-medium">
              <Check size={9} /> OK
            </span>
          </div>
          <div className="p-2.5">
            <div className="flex items-center gap-1.5 mb-0.5">
              <div className="w-3.5 h-3.5 rounded border border-white/20 shrink-0" style={{ backgroundColor: v.color_hex || "#888" }} />
              <span className="text-xs font-mono text-neutral-400">{v.color_hex || "—"}</span>
            </div>
            <p className="text-[10px] font-mono text-neutral-600">#{String(v.id).slice(0, 8)}</p>
          </div>
        </div>
      ))}
    </div>
  );
}

function SEOTab({ seo, copied, copyText, navigate, productId }) {
  if (seo.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-24 text-center">
        <div className="w-16 h-16 rounded-2xl bg-surface-800 border border-surface-700 flex items-center justify-center mb-4">
          <Sparkles size={28} className="text-neutral-600" />
        </div>
        <h3 className="font-display text-lg text-neutral-300 mb-2">Nenhuma descrição SEO</h3>
        <p className="text-sm text-neutral-500 max-w-xs mb-6">
          Gere descrições otimizadas para marketplaces.
        </p>
        <button onClick={() => navigate(`/seo/${productId}`)}
          className="px-4 py-2 bg-amber-500 hover:bg-amber-400 text-surface-950 text-sm font-medium rounded-lg transition-colors">
          Gerar SEO
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {seo.map((s) => (
        <div key={s.platform} className="bg-surface-800 border border-surface-700 rounded-xl p-5 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-amber-400 uppercase tracking-wider">{s.platform}</span>
            <button
              onClick={() => copyText(`${s.title}\n\n${s.description}`, s.platform)}
              className="text-neutral-600 hover:text-amber-400 transition-colors"
              title="Copiar tudo"
            >
              {copied === s.platform ? <Check size={13} className="text-emerald-400" /> : <Copy size={13} />}
            </button>
          </div>
          <div className="bg-surface-700 border border-surface-600 rounded-lg p-3">
            <p className="text-sm font-medium text-neutral-100">{s.title}</p>
          </div>
          <div className="bg-surface-700 border border-surface-600 rounded-lg p-3">
            <p className="text-xs text-neutral-300 whitespace-pre-wrap leading-relaxed">{s.description}</p>
          </div>
          {s.tags.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {s.tags.map((tag, i) => (
                <span key={i} className="text-xs bg-surface-700 border border-surface-600 text-neutral-400 px-2 py-0.5 rounded-full font-mono">
                  {tag}
                </span>
              ))}
            </div>
          )}
          {s.updated_at && (
            <p className="text-[10px] text-neutral-600 font-mono">
              Atualizado: {new Date(s.updated_at).toLocaleString("pt-BR")}
            </p>
          )}
        </div>
      ))}
    </div>
  );
}

function HistoryTab({ stats, navigate, productId }) {
  return (
    <div className="space-y-6">
      <div className="bg-surface-800 border border-surface-700 rounded-xl p-6">
        <p className="text-xs text-neutral-500 uppercase tracking-wider mb-4">Resumo de custos</p>
        <div className="grid grid-cols-3 gap-4">
          <div>
            <p className="text-2xl font-medium text-neutral-100">{stats.total_jobs}</p>
            <p className="text-xs text-neutral-500">Jobs executados</p>
          </div>
          <div>
            <p className="text-2xl font-medium text-amber-400">{stats.total_cost_cents}c</p>
            <p className="text-xs text-neutral-500">Custo em centavos</p>
          </div>
          <div>
            <p className="text-2xl font-medium text-neutral-100">R$ {stats.total_cost_brl.toFixed(2)}</p>
            <p className="text-xs text-neutral-500">Custo em reais</p>
          </div>
        </div>
      </div>
      <button
        onClick={() => navigate("/historico")}
        className="flex items-center gap-2 px-4 py-2 bg-surface-700 hover:bg-surface-600 border border-surface-600 text-neutral-300 rounded-lg text-sm transition-colors"
      >
        <Clock size={14} />
        Ver histórico completo
        <ChevronRight size={14} className="ml-auto" />
      </button>
    </div>
  );
}
