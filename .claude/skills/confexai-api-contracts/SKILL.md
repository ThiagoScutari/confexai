---
name: confexai-api-contracts
description: >
  Contratos de API do ConfexAI. Use esta SKILL sempre que for criar, modificar
  ou revisar endpoints FastAPI, schemas Pydantic, ou convenções de resposta.
  Define os contratos de todos os módulos: produtos, imagens, jobs de geração,
  descrições SEO e vídeos. Também cobre convenções de nomenclatura, estrutura
  de resposta, tratamento de erros e autenticação. Consulte antes de criar
  qualquer endpoint novo ou alterar schemas existentes.
---

# ConfexAI — Contratos de API

## Convenções Gerais

### Base URL
```
/api/v1/
```

### Autenticação
```
Authorization: Bearer <jwt_token>
```
Todos os endpoints exigem autenticação exceto `/api/v1/auth/login`.

### Estrutura de Resposta Padrão

**Sucesso:**
```json
{
  "data": { ... },
  "meta": {
    "timestamp": "2026-03-26T12:00:00Z"
  }
}
```

**Erro:**
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Mensagem legível para o usuário",
    "details": [ ... ]
  }
}
```

**Lista paginada:**
```json
{
  "data": [ ... ],
  "meta": {
    "total": 42,
    "page": 1,
    "per_page": 20,
    "timestamp": "2026-03-26T12:00:00Z"
  }
}
```

### Códigos de Status HTTP
| Situação | Código |
|---|---|
| Criação bem-sucedida | 201 |
| Leitura/atualização bem-sucedida | 200 |
| Job enfileirado (assíncrono) | 202 |
| Validação falhou | 422 |
| Não autorizado | 401 |
| Sem permissão | 403 |
| Não encontrado | 404 |
| Conflito de estado | 409 |
| Erro interno | 500 |

---

## Módulo: Produtos

### POST /api/v1/products
Cria um novo produto.

**Request:**
```json
{
  "name": "Blusa Floral Manga Longa",
  "category": "blusa",
  "fabric": "viscose 100%",
  "notes": "bordado floral no decote"
}
```

**Response 201:**
```json
{
  "data": {
    "id": "uuid",
    "name": "Blusa Floral Manga Longa",
    "category": "blusa",
    "fabric": "viscose 100%",
    "notes": "bordado floral no decote",
    "created_at": "2026-03-26T12:00:00Z"
  }
}
```

**Schema Pydantic:**
```python
class ProductCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=200)
    category: str = Field(..., max_length=50)
    fabric: str = Field(..., max_length=200)
    notes: str | None = Field(None, max_length=1000)

class ProductResponse(BaseModel):
    id: UUID
    name: str
    category: str
    fabric: str
    notes: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
```

---

## Módulo: Imagens

### POST /api/v1/products/{product_id}/images/upload
Upload da imagem original da peça.

**Request:** `multipart/form-data`
```
file: <imagem JPG/PNG>
```

**Regras de validação:**
- Formatos aceitos: `image/jpeg`, `image/png`
- Tamanho máximo: 20MB
- Resolução mínima: 500×500px

**Response 201:**
```json
{
  "data": {
    "id": "uuid",
    "product_id": "uuid",
    "type": "original",
    "original_url": "/uploads/products/{id}/original.jpg",
    "processed_url": null,
    "status": "uploaded",
    "created_at": "2026-03-26T12:00:00Z"
  }
}
```

### POST /api/v1/images/{image_id}/remove-background
Dispara job de remoção de fundo.

**Response 202:**
```json
{
  "data": {
    "job_id": "uuid",
    "type": "background_removal",
    "status": "pending",
    "image_id": "uuid"
  }
}
```

---

## Módulo: Jobs de Geração

### POST /api/v1/jobs
Cria um job de geração (variação de cor, fundo, vídeo).

**Request:**
```json
{
  "product_image_id": "uuid",
  "type": "color_variation",
  "params": {
    "target_colors": ["#FF5733", "#2E86AB", "#A8DADC"],
    "protected_regions": [
      {
        "type": "estampa",
        "bbox": {"x": 120, "y": 80, "width": 200, "height": 180}
      }
    ]
  }
}
```

**Tipos de job válidos:**
| type | Descrição |
|---|---|
| `background_removal` | Remoção de fundo |
| `protected_region_detection` | Detectar estampas/bordados |
| `color_variation` | Variação de cor |
| `background_alternative` | Fundo alternativo |
| `seo_description` | Gerar descrição SEO |
| `video_ugc` | Gerar vídeo UGC |

**Response 202:**
```json
{
  "data": {
    "id": "uuid",
    "product_image_id": "uuid",
    "type": "color_variation",
    "status": "pending",
    "api_used": null,
    "cost_cents": null,
    "created_at": "2026-03-26T12:00:00Z"
  }
}
```

### GET /api/v1/jobs/{job_id}
Consulta status do job (usado pelo frontend em polling a cada 3s).

**Response 200:**
```json
{
  "data": {
    "id": "uuid",
    "type": "color_variation",
    "status": "done",
    "api_used": "gemini",
    "cost_cents": 3,
    "tokens_used": null,
    "result": {
      "output_images": [
        {
          "color_hex": "#FF5733",
          "url": "/outputs/products/{id}/color_ff5733.jpg",
          "png_url": "/outputs/products/{id}/color_ff5733.png"
        }
      ]
    },
    "created_at": "2026-03-26T12:00:00Z",
    "completed_at": "2026-03-26T12:00:14Z"
  }
}
```

**Status possíveis:** `pending` → `processing` → `done` | `failed`

### POST /api/v1/jobs/{job_id}/approve
Aprova um resultado gerado para export.

**Response 200:**
```json
{
  "data": {
    "job_id": "uuid",
    "approved_at": "2026-03-26T12:05:00Z",
    "approved_by": "user_id"
  }
}
```

### POST /api/v1/jobs/{job_id}/reject
Rejeita e permite regeneração.

**Request:**
```json
{
  "reason": "cor ficou muito escura, reduzir intensidade"
}
```

---

## Módulo: Descrições SEO

### POST /api/v1/products/{product_id}/descriptions
Gera descrição SEO via Claude.

**Request:**
```json
{
  "platforms": ["mercadolivre", "shopee", "shopify"],
  "image_id": "uuid"
}
```

**Response 202:** Job criado (mesmo padrão de jobs).

### GET /api/v1/products/{product_id}/descriptions
Lista todas as descrições geradas para o produto.

**Response 200:**
```json
{
  "data": [
    {
      "id": "uuid",
      "platform": "mercadolivre",
      "title": "Blusa Feminina Floral Manga Longa Viscose – Tamanhos P ao GG",
      "description": "...",
      "tags": ["blusa floral", "manga longa", "viscose"],
      "char_count_title": 58,
      "approved": true,
      "created_at": "2026-03-26T12:00:00Z"
    }
  ]
}
```

---

## Módulo: Export

### GET /api/v1/products/{product_id}/export
Gera pacote de assets aprovados para download.

**Query params:**
```
platform=mercadolivre   (opcional — filtra por plataforma)
format=zip              (padrão: zip)
```

**Response 200:** Stream do arquivo ZIP.

**Estrutura do ZIP:**
```
export_{product_id}_{platform}_{date}/
├── images/
│   ├── original_1200x1200.jpg
│   ├── color_ff5733_1200x1200.jpg
│   ├── color_2e86ab_1200x1200.jpg
│   └── background_lifestyle_1200x1200.jpg
├── videos/
│   └── ugc_reel_9x16.mp4
└── descriptions/
    └── mercadolivre.txt
```

---

## Padrão de Endpoint FastAPI

```python
@router.post(
    "/api/v1/products",
    response_model=StandardResponse[ProductResponse],
    status_code=201,
)
async def create_product(
    payload: ProductCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StandardResponse[ProductResponse]:
    try:
        product = Product(**payload.model_dump())
        db.add(product)
        db.commit()
        db.refresh(product)
        return StandardResponse(data=ProductResponse.model_validate(product))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao criar produto: {e}", exc_info=True)
        raise HTTPException(500, detail="Erro interno do servidor.")
```

---

## Nomenclatura

| Convenção | Exemplo |
|---|---|
| Endpoints | kebab-case: `/remove-background` |
| Campos JSON | snake_case: `product_id`, `cost_cents` |
| IDs | UUID v4 |
| Timestamps | ISO 8601 UTC: `2026-03-26T12:00:00Z` |
| Cores | HEX maiúsculo: `#FF5733` |
| Plataformas | lowercase: `mercadolivre`, `shopee`, `shopify` |
