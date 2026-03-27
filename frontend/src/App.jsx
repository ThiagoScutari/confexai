import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./contexts/AuthContext";
import { ToastProvider } from "./components/Toast";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import Produtos from "./pages/Produtos";
import Pipeline from "./pages/Pipeline";
import Resultados from "./pages/Resultados";
import Historico from "./pages/Historico";
import SEO from "./pages/SEO";

function ProtectedRoute({ children }) {
  const { isAuth } = useAuth();
  return isAuth ? children : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <ToastProvider>
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
              <Route path="resultados" element={<Resultados />} />
              <Route path="resultados/:productId" element={<Resultados />} />
              <Route path="historico" element={<Historico />} />
              <Route path="seo/:productId" element={<SEO />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ToastProvider>
  );
}
