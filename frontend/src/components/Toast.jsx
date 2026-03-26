import { useState, useEffect, createContext, useContext, useCallback } from "react";
import { Check, X, AlertCircle, Info } from "lucide-react";

const ToastContext = createContext(null);

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);

  const addToast = useCallback((message, type = "info", duration = 4000) => {
    const id = Date.now();
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, duration);
  }, []);

  const removeToast = (id) => setToasts((prev) => prev.filter((t) => t.id !== id));

  return (
    <ToastContext.Provider value={{ toast: addToast }}>
      {children}
      {/* Toast container */}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 pointer-events-none">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`flex items-center gap-3 px-4 py-3 rounded-lg shadow-xl border pointer-events-auto max-w-sm ${
              t.type === "success" ? "bg-emerald-950 border-emerald-700 text-emerald-300" :
              t.type === "error"   ? "bg-red-950 border-red-800 text-red-300" :
              t.type === "warning" ? "bg-amber-950 border-amber-700 text-amber-300" :
              "bg-surface-800 border-surface-600 text-neutral-200"
            }`}
          >
            {t.type === "success" && <Check size={14} className="shrink-0" />}
            {t.type === "error"   && <AlertCircle size={14} className="shrink-0" />}
            {t.type === "info"    && <Info size={14} className="shrink-0" />}
            <span className="text-sm">{t.message}</span>
            <button
              onClick={() => removeToast(t.id)}
              className="ml-auto opacity-60 hover:opacity-100 transition-opacity"
            >
              <X size={12} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export const useToast = () => useContext(ToastContext);
