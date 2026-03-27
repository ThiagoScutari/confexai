import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Plus, Package, ChevronRight } from "lucide-react";
import { listProducts, createProduct } from "../services/api";
import { useToast } from "../components/Toast";

export default function Produtos() {
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: "", category: "", fabric: "", notes: "" });
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();
  const { toast } = useToast();

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
      toast("Produto criado com sucesso", "success");
    } catch (err) {
      const msg = err.response?.data?.detail || "Erro ao criar produto";
      toast(msg, "error");
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

      {/* Formulario inline */}
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
                placeholder="blusa, calca, vestido..."
              />
            </div>
            <div>
              <label className="block text-xs text-neutral-500 mb-1">Tecido</label>
              <input
                required
                value={form.fabric}
                onChange={(e) => setForm({ ...form, fabric: e.target.value })}
                className="w-full bg-surface-700 border border-surface-600 rounded px-3 py-2 text-sm text-neutral-100 focus:outline-none focus:border-amber-500"
                placeholder="viscose, algodao..."
              />
            </div>
            <div className="col-span-2">
              <label className="block text-xs text-neutral-500 mb-1">Observacoes</label>
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
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="bg-surface-800 border border-surface-700 rounded-lg px-5 py-4 animate-pulse">
              <div className="flex items-center gap-4">
                <div className="w-8 h-8 bg-surface-700 rounded" />
                <div className="space-y-2">
                  <div className="h-3 w-40 bg-surface-700 rounded" />
                  <div className="h-2 w-24 bg-surface-700 rounded" />
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : products.length === 0 ? (
        <div className="text-center py-16 text-neutral-600">
          <Package size={40} className="mx-auto mb-3 opacity-30" />
          <p className="text-sm">Nenhum produto cadastrado</p>
        </div>
      ) : (
        <div className="space-y-2">
          {products.map((p) => (
            <div
              key={p.id}
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
              <div className="flex items-center gap-2">
                <button
                  onClick={() => navigate(`/resultados/${p.id}`)}
                  className="px-3 py-1.5 text-xs bg-surface-700 hover:bg-surface-600 border border-surface-600 text-neutral-300 rounded-md transition-colors"
                >
                  Resultados
                </button>
                <button
                  onClick={() => navigate(`/pipeline/${p.id}`)}
                  className="px-3 py-1.5 text-xs bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/30 text-amber-400 rounded-md transition-colors"
                >
                  Pipeline →
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
