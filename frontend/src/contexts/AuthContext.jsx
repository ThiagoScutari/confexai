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
