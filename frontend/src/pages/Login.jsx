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
          <p className="text-sm text-neutral-500 mt-2">Pipeline de imagens para confeccao</p>
        </div>

        <form onSubmit={handleSubmit} className="bg-surface-800 border border-surface-600 rounded-xl p-8 space-y-4">
          <div>
            <label className="block text-xs text-neutral-500 mb-1.5">E-mail</label>
            <input
              type="email"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              className="input-base"
            />
          </div>
          <div>
            <label className="block text-xs text-neutral-500 mb-1.5">Senha</label>
            <input
              type="password"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              className="input-base"
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
