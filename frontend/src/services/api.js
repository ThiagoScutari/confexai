import axios from "axios";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8002/api/v1";

const api = axios.create({ baseURL: API_BASE });

// Injetar token em todas as requisicoes
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
