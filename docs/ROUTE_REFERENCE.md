# ConfexAI — Mapa de Rotas (ROUTE_REFERENCE.md)

**Versão:** 1.0 — Sprint 14  
**Base URL API:** `http://localhost:8002/api/v1`  
**Base URL Frontend:** `http://localhost:5173`  
**Auth:** `Authorization: Bearer {jwt_token}` em todos os endpoints exceto `/auth/login`

---

## Frontend → Backend: Mapa Completo

### Autenticação

| Página Frontend | Rota Frontend | Método | Endpoint Backend | Auth | Status codes |
|---|---|---|---|---|---|
| Login | `/login` | POST | `/auth/login` | ❌ público | 200, 401 |

---

### Produtos

| Página Frontend | Rota Frontend | Método | Endpoint Backend | Auth | Status codes |
|---|---|---|---|---|---|
| Lista de produtos | `/produtos` | GET | `/products` | ✅ | 200, 401 |
| Criar produto | `/produtos` | POST | `/products` | ✅ | 201, 401, 422 |
| Detalhe (interno) | — | GET | `/products/{id}` | ✅ | 200, 401, 404 |
| Soft delete | — | DELETE | `/products/{id}` | ✅ | 200, 401, 404 |

---

### Imagens

| Página Frontend | Rota Frontend | Método | Endpoint Backend | Auth | Status codes |
|---|---|---|---|---|---|
| Pipeline — upload | `/pipeline/:productId` | POST | `/products/{id}/images/upload?view={view}` | ✅ | 201, 401, 404, 422 |
| Pipeline — remover fundo | `/pipeline/:productId` | POST | `/products/{id}/images/{imageId}/remove-background` | ✅ | 202, 401, 404 |

**Query params do upload:**
- `view`: `frente` | `costas` | `lat_direita` | `lat_esquerda` (opcional)

**Validações de upload:**
- Formatos: `image/jpeg`, `image/png`
- Tamanho: ≤ 20MB
- Resolução: ≥ 500×500px

---

### Jobs de Geração

| Página Frontend | Rota Frontend | Método | Endpoint Backend | Auth | Status codes |
|---|---|---|---|---|---|
| Pipeline — detectar regiões | `/pipeline/:productId` | POST | `/jobs/detect-protected-regions` | ✅ | 202, 401, 404, 422 |
| Pipeline — variação de cor | `/pipeline/:productId` | POST | `/jobs/color-variation` | ✅ | 202, 401, 404 |
| Resultados — listar jobs | `/resultados` | GET | `/jobs` | ✅ | 200, 401 |
| Resultados — aprovar | `/resultados` | POST | `/jobs/{id}/approve` | ✅ | 200, 401, 404, 409 |
| Resultados — rejeitar | `/resultados` | POST | `/jobs/{id}/reject` | ✅ | 200, 401, 404 |
| Resultados — arquivar | `/resultados` | PATCH | `/jobs/{id}/archive` | ✅ | 200, 401, 404 |
| Resultados — desarquivar | `/resultados` | PATCH | `/jobs/{id}/unarchive` | ✅ | 200, 401, 404 |
| Resultados — job individual | — | GET | `/jobs/{id}` | ✅ | 200, 401, 404 |
| Resultados — limpeza | — | DELETE | `/jobs/cleanup-broken` | ✅ | 200, 401 |
| Histórico | `/historico` | GET | `/jobs/history` | ✅ | 200, 401 |

**Query params de `/jobs`:**
- `product_id`: UUID (opcional)
- `type`: `color_variation` | `protected_region_detection` | `background_removal` | `seo_description` | `video_ugc`
- `status`: `pending` | `processing` | `done` | `failed` | `pending_review` | `approved` | `rejected`
- `include_archived`: `true` | `false` (default: false)

**Query params de `/jobs/history`:**
- `product_id`: UUID (opcional)
- `limit`: integer (default: 50, max: 200)

**Body de `/jobs/detect-protected-regions`:**
```json
{ "product_image_id": "uuid" }
```

**Body de `/jobs/color-variation`:**
```json
{
  "product_image_id": "uuid",
  "target_colors": ["#696980", "#978b7b"],
  "protected_regions": []
}
```

**Body de `/jobs/{id}/reject`:**
```json
{ "reason": "string" }
```

---

### Export (Download)

| Página Frontend | Rota Frontend | Método | Endpoint Backend | Auth | Retorno |
|---|---|---|---|---|---|
| Resultados — baixar produto | `/resultados` | GET | `/jobs/export/{product_id}` | ✅ | ZIP stream |
| Resultados — baixar múltiplos | `/resultados` | POST | `/jobs/export/bulk` | ✅ | ZIP stream |

**Query params de `/jobs/export/{product_id}`:**
- `status`: `approved` (default) | `all`

**Body de `/jobs/export/bulk`:**
```json
{
  "product_ids": ["uuid1", "uuid2"],
  "status": "approved"
}
```

---

### SEO

| Página Frontend | Rota Frontend | Método | Endpoint Backend | Auth | Status codes |
|---|---|---|---|---|---|
| SEO — gerar | `/seo/:productId` | POST | `/products/{id}/seo` | ✅ | 202, 401, 404, 422, 429 |
| SEO — listar | `/seo/:productId` | GET | `/products/{id}/seo` | ✅ | 200, 401, 404 |

**Body de `POST /products/{id}/seo`:**
```json
{
  "platforms": ["mercadolivre", "shopee", "shopify"],
  "colors": ["#696980", "#978b7b"],
  "image_id": null
}
```

**Rate limit:** 429 se < 30s desde última geração para o mesmo produto.

---

### Static Files (sem autenticação)

| Recurso | Padrão de URL | Exemplo |
|---|---|---|
| Imagem original | `/static/uploads/{product_id}/original_{view}.{ext}` | `/static/uploads/abc.../original_frente.png` |
| Variação de cor PNG | `/static/uploads/{product_id}/color_{HEX}_{view}.png` | `/static/uploads/abc.../color_696980_frente.png` |
| Variação de cor JPG | `/static/uploads/{product_id}/color_{HEX}_{view}.jpg` | `/static/uploads/abc.../color_696980_frente.jpg` |

---

## Frontend: Rotas Internas

| Página | Rota | Proteção | Componente |
|---|---|---|---|
| Login | `/login` | público | `Login.jsx` |
| Lista de produtos | `/produtos` | ✅ auth | `Produtos.jsx` |
| Pipeline | `/pipeline/:productId` | ✅ auth | `Pipeline.jsx` |
| Resultados (todos) | `/resultados` | ✅ auth | `Resultados.jsx` |
| Resultados (produto) | `/resultados/:productId` | ✅ auth | `Resultados.jsx` |
| Histórico | `/historico` | ✅ auth | `Historico.jsx` |
| SEO | `/seo/:productId` | ✅ auth | `SEO.jsx` |
| Raiz | `/` | ✅ auth | redirect → `/produtos` |

---

## Serviço de API — `frontend/src/services/api.js`

```javascript
// Funções disponíveis (referência rápida)
login(email, password)
listProducts()
createProduct(data)
getProduct(id)
uploadImage(productId, file, view)
removeBackground(productId, imageId)
detectProtectedRegions(productImageId)
createColorVariation(productImageId, colors, regions)
getJob(jobId)
listJobs(productId, type, status, includeArchived)
approveJob(jobId)
rejectJob(jobId, reason)
archiveJob(jobId)
unarchiveJob(jobId)
pollJob(jobId, onUpdate, maxAttempts, intervalMs)
getHistory(productId, limit)
generateSEO(productId, platforms, colors, imageId)
getSEO(productId)
```

---

## Permissões por Endpoint

| Endpoint | Nível mínimo |
|---|---|
| Todos os endpoints | `admin` (MVP — único usuário) |
| `/auth/login` | público |
| `/static/uploads/**` | público (sem auth) |

> No MVP, há apenas um usuário administrador configurado via variáveis de ambiente (`ADMIN_EMAIL`, `ADMIN_PASSWORD_HASH`). Multi-tenant é planejado para Fase 3.

---

## Erros Padrão

| Código | Quando ocorre |
|---|---|
| 400 | Regra de negócio violada (ex: aprovar job que não está em revisão) |
| 401 | Token ausente ou expirado |
| 403 | Token válido mas sem permissão |
| 404 | Recurso não encontrado ou soft-deleted |
| 409 | Conflito de estado (ex: aprovar job já aprovado) |
| 422 | Validação Pydantic falhou (body inválido) |
| 429 | Rate limit atingido |
| 500 | Erro interno — ver logs da API |

**Formato de erro padrão:**
```json
{
  "detail": "Mensagem legível para o usuário"
}
```

**Formato de sucesso padrão:**
```json
{
  "data": { ... }
}
```
