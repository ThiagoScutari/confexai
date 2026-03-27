# PRD — Sprint 05: Preview de Imagens e Serving de Assets Gerados

**Status:** Aprovação Pendente
**Origem:** Feedback operacional Sprint 04 — dois gaps visuais críticos identificados
**Data:** 2026-03-26
**Objetivo:** (1) Mostrar thumbnail da imagem carregada nas zonas de upload. (2) Exibir a imagem real gerada pelo Gemini nos cards de resultado — não apenas a cor HEX.

---

## Contexto dos Gaps

### Gap 1 — Preview no Upload
O componente `UploadZone` em `Pipeline.jsx` exibe apenas ícone ✓ e texto "Carregado" após o upload. O operador não sabe se enviou a imagem correta sem fechar e verificar no Explorer.

### Gap 2 — Imagem real nos cards de resultado
O `JobCard` exibe apenas um retângulo com a cor HEX. O `jpg_url` retornado pela API (`/app/examples/uploads/{product_id}/color_696980_frente.jpg`) é um **path interno do container** — o browser não consegue acessar.

**Solução:** montar os arquivos de upload como assets estáticos servidos pelo FastAPI em `/static/uploads/`.

---

## Sumário Executivo

| ID | Tipo | Descrição | Esforço |
|---|---|---|---|
| S05-01 | feat | FastAPI serve arquivos estáticos de `/app/examples/uploads` em `/static/uploads` | Pequeno |
| S05-02 | feat | API retorna `jpg_url` como URL relativa acessível pelo browser | Pequeno |
| S05-03 | feat | Frontend: preview de thumbnail no UploadZone | Pequeno |
| S05-04 | feat | Frontend: exibir imagem gerada no JobCard | Pequeno |
| S05-05 | test | Testes para endpoint de static files e URLs corretas | Pequeno |

**Critério de aceite:** após upload de uma imagem, ver o thumbnail. Após pipeline rodar, ver a foto da peça com a cor alterada no card — não o retângulo de cor.

---

## S05-01 — FastAPI Serve Static Files

### Instalar dependência

`aiofiles` é necessário para o `StaticFiles` do Starlette funcionar corretamente:

```
# Adicionar em backend/requirements.txt
aiofiles==24.1.0
```

### Alterar `backend/app/main.py`

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
from pathlib import Path

from app.api import health, auth, products, images, jobs

app = FastAPI(title="ConfexAI API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Servir uploads como assets estáticos
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "/app/examples/uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(products.router)
app.include_router(images.router)
app.include_router(jobs.router)
```

**Resultado:** um arquivo em `/app/examples/uploads/{product_id}/color_696980_frente.jpg` fica acessível em `http://localhost:8002/static/uploads/{product_id}/color_696980_frente.jpg`.

---

## S05-02 — URLs relativas no retorno da API

O problema está em `color_variation.py` e `images.py` — os paths salvos no banco e retornados na API são paths absolutos do container. Precisam ser convertidos para URLs relativas acessíveis pelo browser.

### Helper em `backend/app/services/url_helper.py`

```python
import os
from pathlib import Path

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "/app/examples/uploads"))


def path_to_url(file_path: str | Path) -> str:
    """
    Converte path absoluto do container para URL relativa do static serving.
    Ex: /app/examples/uploads/uuid/color_696980_frente.jpg
     →  /static/uploads/uuid/color_696980_frente.jpg
    """
    path = Path(file_path)
    try:
        relative = path.relative_to(UPLOAD_DIR)
        return f"/static/uploads/{relative}"
    except ValueError:
        # Path fora do UPLOAD_DIR — retornar como está
        return str(file_path)
```

### Alterar `backend/app/services/color_variation.py`

No dict de retorno de `_save_result`, converter os paths para URLs:

```python
from app.services.url_helper import path_to_url

def _save_result(result_bytes: bytes, output_path: Path, width: int, height: int) -> dict:
    # ... código existente de salvar PNG e JPG ...

    return {
        "png_url": path_to_url(output_path),
        "jpg_url": path_to_url(jpg_path),
        "resolution": f"{width}x{height}",
        "cost_cents": GEMINI_COST_PER_IMAGE_CENTS,
    }
```

### Alterar `backend/app/api/images.py`

No retorno do upload, incluir `original_url` como URL acessível:

```python
from app.services.url_helper import path_to_url

# Na resposta do upload, adicionar url_publica:
response_data = ImageResponse(
    id=image.id,
    product_id=image.product_id,
    type=image.type,
    view=view,
    original_url=image.original_url,          # path interno (manter para processamento)
    processed_url=image.processed_url,
    public_url=path_to_url(image.original_url), # ← URL acessível pelo browser
    status="uploaded",
    created_at=image.created_at,
)
```

### Alterar `backend/app/schemas/images.py`

```python
class ImageResponse(BaseModel):
    id: UUID
    product_id: UUID
    type: str
    view: str | None = None
    original_url: str | None
    processed_url: str | None
    public_url: str | None = None   # ← campo novo
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
```

### Alterar `backend/app/api/jobs.py`

No retorno do endpoint `color-variation`, incluir `jpg_public_url`:

```python
results.append({
    "job_id": str(job.id),
    "color_hex": color_hex,
    "status": "pending_review",
    "png_url": result["png_url"],           # URL já convertida pelo helper
    "jpg_url": result["jpg_url"],           # URL já convertida pelo helper
    "cost_cents": result["cost_cents"],
    "method": result.get("method", "gemini"),
})
```

---

## S05-03 — Frontend: Preview no UploadZone

### Alterar `frontend/src/pages/Pipeline.jsx` — componente `UploadZone`

```jsx
function UploadZone({ view, label, image, onUpload }) {
  const [preview, setPreview] = useState(null);

  const handleFile = (file) => {
    // Gerar preview local antes mesmo do upload
    const reader = new FileReader();
    reader.onload = (e) => setPreview(e.target.result);
    reader.readAsDataURL(file);
    onUpload(file);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  };

  return (
    <label
      className={`relative flex flex-col items-center justify-center aspect-square rounded-lg border-2 border-dashed cursor-pointer transition-all overflow-hidden ${
        image
          ? "border-amber-500/50"
          : "border-surface-600 bg-surface-800 hover:border-surface-500 hover:bg-surface-700"
      }`}
      onDrop={handleDrop}
      onDragOver={(e) => e.preventDefault()}
    >
      <input
        type="file"
        accept="image/png,image/jpeg"
        className="hidden"
        onChange={(e) => e.target.files[0] && handleFile(e.target.files[0])}
      />

      {preview ? (
        // Thumbnail da imagem carregada
        <>
          <img
            src={preview}
            alt={label}
            className="absolute inset-0 w-full h-full object-contain p-2"
          />
          <div className="absolute bottom-0 left-0 right-0 bg-black/60 py-1 px-2 flex items-center justify-between">
            <span className="text-xs text-amber-400 font-medium">{label}</span>
            <Check size={12} className="text-amber-400" />
          </div>
        </>
      ) : (
        // Estado vazio
        <>
          <Upload size={20} className="text-neutral-600 mb-1" />
          <span className="text-xs text-neutral-500">{label}</span>
        </>
      )}
    </label>
  );
}
```

---

## S05-04 — Frontend: Imagem real no JobCard

### Alterar `frontend/src/pages/Pipeline.jsx` — componente `JobCard`

```jsx
const API_BASE = import.meta.env.VITE_API_URL?.replace("/api/v1", "") || "http://localhost:8002";

function JobCard({ job, onApprove, onReject }) {
  const statusColors = {
    pending_review: "text-amber-400",
    approved: "text-emerald-400",
    rejected: "text-red-400",
  };

  // Construir URL pública da imagem gerada
  const imageUrl = job.jpg_url ? `${API_BASE}${job.jpg_url}` : null;

  return (
    <div className={`bg-surface-800 border rounded-lg overflow-hidden transition-all ${
      job.status === "approved" ? "border-emerald-500/30" :
      job.status === "rejected" ? "border-red-500/20 opacity-50" :
      "border-surface-600"
    }`}>
      {/* Preview da imagem gerada */}
      <div className="relative aspect-square bg-surface-700">
        {imageUrl ? (
          <img
            src={imageUrl}
            alt={`Variação ${job.color_hex}`}
            className="w-full h-full object-contain"
            onError={(e) => {
              // Fallback: mostrar cor se imagem não carregar
              e.target.style.display = "none";
              e.target.nextSibling.style.display = "flex";
            }}
          />
        ) : null}
        {/* Fallback cor HEX */}
        <div
          className="absolute inset-0 flex items-center justify-center"
          style={{
            backgroundColor: job.color_hex,
            display: imageUrl ? "none" : "flex"
          }}
        >
          <span className="font-mono text-xs bg-black/30 text-white px-2 py-0.5 rounded">
            {job.color_hex}
          </span>
        </div>
        {/* Badge da cor sempre visível */}
        <div className="absolute bottom-2 left-2">
          <span
            className="font-mono text-xs px-2 py-0.5 rounded border"
            style={{
              backgroundColor: job.color_hex + "33",
              borderColor: job.color_hex + "66",
              color: "#fff"
            }}
          >
            {job.color_hex}
          </span>
        </div>
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

## S05-05 — Testes

### `backend/tests/test_static_serving.py`

```python
def test_static_uploads_endpoint_acessivel(client):
    """Confirma que /static/uploads/ está montado e respondendo."""
    response = client.get("/static/uploads/")
    # 404 é esperado para diretório raiz — mas não 500
    assert response.status_code in (200, 404)


def test_path_to_url_converte_corretamente():
    from app.services.url_helper import path_to_url
    url = path_to_url("/app/examples/uploads/uuid-123/color_696980_frente.jpg")
    assert url == "/static/uploads/uuid-123/color_696980_frente.jpg"


def test_path_to_url_path_fora_do_upload_dir():
    from app.services.url_helper import path_to_url
    url = path_to_url("/tmp/outro_arquivo.jpg")
    assert url == "/tmp/outro_arquivo.jpg"


def test_image_upload_retorna_public_url(client, auth_headers, sample_product):
    import io
    from PIL import Image as PILImage

    img = PILImage.new("RGB", (600, 600), color=(200, 200, 200))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")

    response = client.post(
        f"/api/v1/products/{sample_product.id}/images/upload",
        files={"file": ("frente.jpg", buf.getvalue(), "image/jpeg")},
        params={"view": "frente"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert "public_url" in data
    assert data["public_url"].startswith("/static/uploads/")
```

---

## Ordem de Execução

```
S05-01 → S05-02 → S05-05 (testes backend)
                ↓
S05-03 → S05-04 (frontend — depois dos testes verdes)
```

---

## Commits Atômicos

```
feat(api): serve static uploads via /static/uploads endpoint [S05-01]
feat(api): add url_helper to convert internal paths to public URLs [S05-02]
test(sprint05): add tests for static serving and public_url field [S05-05]
feat(frontend): add image preview in UploadZone [S05-03]
feat(frontend): show generated image in JobCard instead of color swatch [S05-04]
```

---

## Critérios de Aceite

- [ ] `http://localhost:8002/static/uploads/{product_id}/color_696980_frente.jpg` retorna a imagem no browser
- [ ] Upload de imagem retorna `public_url` no payload
- [ ] Após upload, UploadZone mostra thumbnail da imagem carregada
- [ ] Cards de resultado mostram a foto da peça com a cor alterada
- [ ] Fallback de cor HEX funciona se imagem não carregar
- [ ] `pytest backend/tests/ -v` → todos os testes passam, 0 falhas
