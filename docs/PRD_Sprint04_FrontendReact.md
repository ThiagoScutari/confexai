# PRD — Sprint 04: Frontend React — Interface de Operação do Pipeline

**Status:** Aprovação Pendente
**Origem:** Feature — interface visual para operar o pipeline sem depender de curl/scripts
**Data:** 2026-03-26
**Objetivo:** Interface React funcional e visualmente refinada para criar produtos, fazer upload de imagens, disparar o pipeline de variação de cor e revisar/aprovar resultados.

---

## Princípios de Design

**Contexto:** ferramenta profissional para confecção têxtil. O operador é técnico (Thiago), trabalha com imagens de produto e precisa de clareza operacional — não de entretenimento.

**Direção estética:** **Industrial refinado** — paleta escura com acentos em âmbar/dourado, tipografia editorial, grid rigoroso. Inspira confiança técnica. Pensa em ferramentas como Figma, Linear, Vercel Dashboard — funcionais e belas ao mesmo tempo.

**O que torna memorável:** a galeria de resultados com as variações de cor lado a lado, mostrando a mesma peça em 3 tons com aprovação por clique.

---

## Sumário Executivo

| ID | Tipo | Descrição | Esforço |
|---|---|---|---|
| S04-01 | devops | Configurar Vite + React + TailwindCSS + React Router | Pequeno |
| S04-02 | feat | Layout base: Sidebar + Header + área de conteúdo | Pequeno |
| S04-03 | feat | Página: Lista de produtos + criar produto | Médio |
| S04-04 | feat | Página: Upload de imagens (4 views) + trigger do pipeline | Médio |
| S04-05 | feat | Página: Galeria de resultados com aprovação/rejeição | Médio |
| S04-06 | feat | Serviço de API (axios) + contexto de autenticação | Pequeno |

**Critério de aceite:** conseguir criar um produto, subir as 4 imagens de `examples/roupa/`, disparar detecção + variação de cor, e aprovar os resultados — tudo pela interface, sem curl.

---

## S04-01 — Setup Vite + React + TailwindCSS

### Dependências a instalar no `frontend/`

```json
{
  "dependencies": {
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "react-router-dom": "^6.26.0",
    "axios": "^1.7.0",
    "lucide-react": "^0.447.0"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.3.0",
    "tailwindcss": "^3.4.0",
    "autoprefixer": "^10.4.0",
    "postcss": "^8.4.0"
  }
}
```

### `frontend/tailwind.config.js`

```javascript
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        // Paleta Industrial Refinado
        surface: {
          950: "#0a0a0b",
          900: "#111113",
          800: "#1a1a1f",
          700: "#242429",
          600: "#2e2e35",
        },
        amber: {
          400: "#fbbf24",
          500: "#f59e0b",
          600: "#d97706",
        },
        neutral: {
          100: "#f5f5f4",
          200: "#e7e5e4",
          400: "#a8a29e",
          500: "#78716c",
          600: "#57534e",
        }
      },
      fontFamily: {
        display: ["'DM Serif Display'", "serif"],
        body: ["'DM Sans'", "sans-serif"],
        mono: ["'JetBrains Mono'", "monospace"],
      },
    },
  },
  plugins: [],
}
```

### `frontend/index.html` — adicionar Google Fonts

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&family=DM+Serif+Display&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
```

---

## S04-06 — Serviço de API e Autenticação (fazer primeiro)

### `frontend/src/services/api.js`

```javascript
import axios from "axios";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8002/api/v1";

const api = axios.create({ baseURL: API_BASE });

// Injetar token em todas as requisições
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("confexai_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Redirecionar para login em 401
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem("confexai_token");
      window.location.href = "/login";
    }
    return Promise.reject(err);
  }
);

export default api;

// Auth
export const login = (email, password) =>
  api.post("/auth/login", { email, password });

// Products
export const listProducts = () => api.get("/products");
export const createProduct = (data) => api.post("/products", data);
export const getProduct = (id) => api.get(`/products/${id}`);

// Images
export const uploadImage = (productId, file, view) => {
  const form = new FormData();
  form.append("file", file);
  return api.post(
    `/products/${productId}/images/upload${view ? `?view=${view}` : ""}`,
    form,
    { headers: { "Content-Type": "multipart/form-data" } }
  );
};
export const removeBackground = (productId, imageId) =>
  api.post(`/products/${productId}/images/${imageId}/remove-background`);

// Jobs
export const detectProtectedRegions = (productImageId) =>
  api.post("/jobs/detect-protected-regions", { product_image_id: productImageId });
export const createColorVariation = (productImageId, colors, regions = []) =>
  api.post("/jobs/color-variation", {
    product_image_id: productImageId,
    target_colors: colors,
    protected_regions: regions,
  });
export const getJob = (jobId) => api.get(`/jobs/${jobId}`);
export const approveJob = (jobId) => api.post(`/jobs/${jobId}/approve`);
export const rejectJob = (jobId, reason) =>
  api.post(`/jobs/${jobId}/reject`, { reason });
```

### `frontend/src/contexts/AuthContext.jsx`

```jsx
import { createContext, useContext, useState, useEffect } from "react";
import { login as apiLogin } from "../services/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(localStorage.getItem("confexai_token"));
  const [loading, setLoading] = useState(false);

  const login = async (email, password) => {
    setLoading(true);
    try {
      const res = await apiLogin(email, password);
      const t = res.data.data.access_token;
      localStorage.setItem("confexai_token", t);
      setToken(t);
      return { ok: true };
    } catch (err) {
      return { ok: false, error: err.response?.data?.detail || "Erro ao fazer login" };
    } finally {
      setLoading(false);
    }
  };

  const logout = () => {
    localStorage.removeItem("confexai_token");
    setToken(null);
  };

  return (
    <AuthContext.Provider value={{ token, login, logout, loading, isAuth: !!token }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
```

---

## S04-02 — Layout Base

### `frontend/src/components/Layout.jsx`

```jsx
import { NavLink, Outlet } from "react-router-dom";
import { Package, Images, LogOut, Zap } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";

const navItems = [
  { to: "/produtos", icon: Package, label: "Produtos" },
  { to: "/pipeline", icon: Zap, label: "Pipeline" },
];

export default function Layout() {
  const { logout } = useAuth();

  return (
    <div className="flex h-screen bg-surface-950 text-neutral-100 font-body">
      {/* Sidebar */}
      <aside className="w-56 bg-surface-900 border-r border-surface-700 flex flex-col">
        {/* Logo */}
        <div className="px-6 py-5 border-b border-surface-700">
          <span className="font-display text-xl text-amber-400">Confex</span>
          <span className="font-display text-xl text-neutral-100">AI</span>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-4 space-y-1">
          {navItems.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-all ${
                  isActive
                    ? "bg-amber-500/10 text-amber-400 font-medium"
                    : "text-neutral-400 hover:text-neutral-100 hover:bg-surface-700"
                }`
              }
            >
              <Icon size={16} />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* Footer */}
        <div className="px-3 py-4 border-t border-surface-700">
          <button
            onClick={logout}
            className="flex items-center gap-3 px-3 py-2 w-full rounded-md text-sm text-neutral-400 hover:text-red-400 hover:bg-surface-700 transition-all"
          >
            <LogOut size={16} />
            Sair
          </button>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}
```

---

## S04-03 — Página: Produtos

### `frontend/src/pages/Produtos.jsx`

```jsx
import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Plus, Package, ChevronRight } from "lucide-react";
import { listProducts, createProduct } from "../services/api";

export default function Produtos() {
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: "", category: "", fabric: "", notes: "" });
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    listProducts()
      .then((r) => setProducts(r.data.data))
      .finally(() => setLoading(false));
  }, []);

  const handleCreate = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await createProduct(form);
      const r = await listProducts();
      setProducts(r.data.data);
      setShowForm(false);
      setForm({ name: "", category: "", fabric: "", notes: "" });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="font-display text-2xl text-neutral-100">Produtos</h1>
          <p className="text-sm text-neutral-500 mt-1">{products.length} cadastrados</p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="flex items-center gap-2 px-4 py-2 bg-amber-500 hover:bg-amber-400 text-surface-950 rounded-md text-sm font-medium transition-colors"
        >
          <Plus size={16} />
          Novo produto
        </button>
      </div>

      {/* Formulário inline */}
      {showForm && (
        <form onSubmit={handleCreate} className="bg-surface-800 border border-surface-600 rounded-lg p-6 mb-6 space-y-4">
          <h2 className="text-sm font-medium text-neutral-300 uppercase tracking-wider">Novo produto</h2>
          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2">
              <label className="block text-xs text-neutral-500 mb-1">Nome</label>
              <input
                required
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                className="w-full bg-surface-700 border border-surface-600 rounded px-3 py-2 text-sm text-neutral-100 focus:outline-none focus:border-amber-500"
                placeholder="Ex: Blusa Floral Manga Longa"
              />
            </div>
            <div>
              <label className="block text-xs text-neutral-500 mb-1">Categoria</label>
              <input
                required
                value={form.category}
                onChange={(e) => setForm({ ...form, category: e.target.value })}
                className="w-full bg-surface-700 border border-surface-600 rounded px-3 py-2 text-sm text-neutral-100 focus:outline-none focus:border-amber-500"
                placeholder="blusa, calça, vestido..."
              />
            </div>
            <div>
              <label className="block text-xs text-neutral-500 mb-1">Tecido</label>
              <input
                required
                value={form.fabric}
                onChange={(e) => setForm({ ...form, fabric: e.target.value })}
                className="w-full bg-surface-700 border border-surface-600 rounded px-3 py-2 text-sm text-neutral-100 focus:outline-none focus:border-amber-500"
                placeholder="viscose, algodão..."
              />
            </div>
            <div className="col-span-2">
              <label className="block text-xs text-neutral-500 mb-1">Observações</label>
              <input
                value={form.notes}
                onChange={(e) => setForm({ ...form, notes: e.target.value })}
                className="w-full bg-surface-700 border border-surface-600 rounded px-3 py-2 text-sm text-neutral-100 focus:outline-none focus:border-amber-500"
                placeholder="Opcional"
              />
            </div>
          </div>
          <div className="flex gap-3 pt-2">
            <button
              type="submit"
              disabled={submitting}
              className="px-4 py-2 bg-amber-500 hover:bg-amber-400 disabled:opacity-50 text-surface-950 rounded text-sm font-medium transition-colors"
            >
              {submitting ? "Salvando..." : "Criar produto"}
            </button>
            <button
              type="button"
              onClick={() => setShowForm(false)}
              className="px-4 py-2 bg-surface-700 hover:bg-surface-600 text-neutral-300 rounded text-sm transition-colors"
            >
              Cancelar
            </button>
          </div>
        </form>
      )}

      {/* Lista */}
      {loading ? (
        <div className="text-sm text-neutral-500">Carregando...</div>
      ) : products.length === 0 ? (
        <div className="text-center py-16 text-neutral-600">
          <Package size={40} className="mx-auto mb-3 opacity-30" />
          <p className="text-sm">Nenhum produto cadastrado</p>
        </div>
      ) : (
        <div className="space-y-2">
          {products.map((p) => (
            <button
              key={p.id}
              onClick={() => navigate(`/pipeline/${p.id}`)}
              className="w-full flex items-center justify-between bg-surface-800 hover:bg-surface-700 border border-surface-600 hover:border-surface-500 rounded-lg px-5 py-4 transition-all group"
            >
              <div className="flex items-center gap-4">
                <div className="w-8 h-8 bg-amber-500/10 rounded flex items-center justify-center">
                  <Package size={16} className="text-amber-400" />
                </div>
                <div className="text-left">
                  <p className="text-sm font-medium text-neutral-100">{p.name}</p>
                  <p className="text-xs text-neutral-500 mt-0.5">{p.category} · {p.fabric}</p>
                </div>
              </div>
              <ChevronRight size={16} className="text-neutral-600 group-hover:text-neutral-400 transition-colors" />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
```

---

## S04-04 — Página: Pipeline

### `frontend/src/pages/Pipeline.jsx`

```jsx
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

      // Detectar regiões protegidas
      await detectProtectedRegions(img.id).catch(() => {});

      // Gerar variações de cor
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
              1 — Imagens da peça
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

          {/* Botão de execução */}
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

      {/* Info + ações */}
      <div className="p-3">
        <div className="flex items-center justify-between mb-2">
          <span className={`text-xs font-medium ${statusColors[job.status] || "text-neutral-400"}`}>
            {job.status === "pending_review" ? "Aguardando revisão" :
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
```

---

## S04-05 — Página: Login

### `frontend/src/pages/Login.jsx`

```jsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: "admin@confexai.local", password: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    const res = await login(form.email, form.password);
    if (res.ok) {
      navigate("/produtos");
    } else {
      setError(res.error);
    }
    setLoading(false);
  };

  return (
    <div className="min-h-screen bg-surface-950 flex items-center justify-center font-body">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <h1 className="font-display text-4xl">
            <span className="text-amber-400">Confex</span>
            <span className="text-neutral-100">AI</span>
          </h1>
          <p className="text-sm text-neutral-500 mt-2">Pipeline de imagens para confecção</p>
        </div>

        <form onSubmit={handleSubmit} className="bg-surface-800 border border-surface-600 rounded-xl p-8 space-y-4">
          <div>
            <label className="block text-xs text-neutral-500 mb-1.5">E-mail</label>
            <input
              type="email"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              className="w-full bg-surface-700 border border-surface-600 rounded-lg px-4 py-2.5 text-sm text-neutral-100 focus:outline-none focus:border-amber-500 transition-colors"
            />
          </div>
          <div>
            <label className="block text-xs text-neutral-500 mb-1.5">Senha</label>
            <input
              type="password"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              className="w-full bg-surface-700 border border-surface-600 rounded-lg px-4 py-2.5 text-sm text-neutral-100 focus:outline-none focus:border-amber-500 transition-colors"
              placeholder="admin123"
            />
          </div>
          {error && <p className="text-xs text-red-400">{error}</p>}
          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 bg-amber-500 hover:bg-amber-400 disabled:opacity-50 text-surface-950 rounded-lg font-medium text-sm transition-colors"
          >
            {loading ? "Entrando..." : "Entrar"}
          </button>
        </form>
      </div>
    </div>
  );
}
```

---

## S04-App — App.jsx e main.jsx

### `frontend/src/App.jsx`

```jsx
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./contexts/AuthContext";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import Produtos from "./pages/Produtos";
import Pipeline from "./pages/Pipeline";

function ProtectedRoute({ children }) {
  const { isAuth } = useAuth();
  return isAuth ? children : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }
          >
            <Route index element={<Navigate to="/produtos" replace />} />
            <Route path="produtos" element={<Produtos />} />
            <Route path="pipeline/:productId" element={<Pipeline />} />
            <Route path="pipeline" element={<Produtos />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
```

### `frontend/src/main.jsx`

```jsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import App from "./App";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <App />
  </StrictMode>
);
```

### `frontend/src/index.css`

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

* { box-sizing: border-box; }
body { margin: 0; -webkit-font-smoothing: antialiased; }
```

---

## Ordem de Execução

```
S04-01 (setup deps + tailwind)
  ↓
S04-06 (api service + auth context — base para tudo)
  ↓
S04-02 (layout)
  ↓
S04-05 (login)
  ↓
S04-03 (produtos)
  ↓
S04-04 (pipeline)
  ↓
App.jsx + main.jsx + index.css
  ↓
docker compose up -d --build
```

---

## Variáveis de ambiente frontend

### `frontend/.env`

```
VITE_API_URL=http://localhost:8002/api/v1
```

---

## Commits Atômicos

```
feat(frontend): setup Vite React TailwindCSS with DM fonts and dark theme [S04-01]
feat(frontend): add API service layer and AuthContext [S04-06]
feat(frontend): add Layout component with sidebar navigation [S04-02]
feat(frontend): add Login page [S04-05]
feat(frontend): add Produtos page with create form [S04-03]
feat(frontend): add Pipeline page with upload, color variation and approval [S04-04]
```

---

## Critérios de Aceite

- [ ] `localhost:5173` carrega interface de login
- [ ] Login com `admin@confexai.local` / `admin123` redireciona para produtos
- [ ] Criar produto novo funciona e aparece na lista
- [ ] Clicar no produto abre a página de pipeline
- [ ] Upload das 4 views funciona com drag & drop ou clique
- [ ] Botão "Executar pipeline" dispara detecção + variação de cor
- [ ] Cards de resultado aparecem com a cor e botões de aprovar/rejeitar
- [ ] Aprovar job muda card para verde
