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
export const listJobs = (productId = null, type = null, status = null, includeArchived = false) => {
  const params = {};
  if (productId) params.product_id = productId;
  if (type) params.type = type;
  if (status) params.status = status;
  if (includeArchived) params.include_archived = true;
  return api.get("/jobs", { params });
};
export const getHistory = (productId = null, limit = 50) => {
  const params = { limit };
  if (productId) params.product_id = productId;
  return api.get("/jobs/history", { params });
};
export const archiveJob = (jobId) =>
  api.patch(`/jobs/${jobId}/archive`);
export const unarchiveJob = (jobId) =>
  api.patch(`/jobs/${jobId}/unarchive`);

// Polling
export const pollJob = (jobId, onUpdate, maxAttempts = 30, intervalMs = 2000) =>
  new Promise((resolve, reject) => {
    let attempts = 0;
    const interval = setInterval(async () => {
      attempts++;
      try {
        const res = await getJob(jobId);
        const job = res.data.data;
        onUpdate(job);
        if (job.status === "done" || job.status === "pending_review" ||
            job.status === "failed") {
          clearInterval(interval);
          resolve(job);
        }
        if (attempts >= maxAttempts) {
          clearInterval(interval);
          reject(new Error("Timeout aguardando job"));
        }
      } catch (err) {
        clearInterval(interval);
        reject(err);
      }
    }, intervalMs);
  });

// SEO
export const generateSEO = (productId, platforms, colors, imageId = null) =>
  api.post(`/products/${productId}/seo`, {
    platforms,
    colors,
    image_id: imageId,
  });
export const getSEO = (productId) =>
  api.get(`/products/${productId}/seo`);
