# PRD — Sprint 01: Fundação do Projeto

**Status:** Aprovação Pendente  
**Origem:** Setup inicial — MVP ConfexAI  
**Data:** 2026-03-26  
**Objetivo:** Ter o projeto rodando localmente com estrutura completa, banco de dados criado, upload de imagem funcionando e testes verdes.

---

## Sumário Executivo

| ID | Tipo | Descrição | Esforço |
|---|---|---|---|
| S01-01 | devops | Estrutura de pastas + Docker Compose (FastAPI + PostgreSQL + React) | Médio |
| S01-02 | feat | Modelos ORM + migration Sprint 01 (4 tabelas) | Pequeno |
| S01-03 | feat | Autenticação JWT (login + middleware) | Médio |
| S01-04 | feat | CRUD de produtos (`POST`, `GET`, `GET /{id}`) | Pequeno |
| S01-05 | feat | Upload de imagem original com validação | Médio |
| S01-06 | test | Testes para todos os endpoints acima | Médio |

**Critério de aceite do sprint:** `docker-compose up` sobe tudo, migration roda, todos os testes passam, upload de JPG funciona via curl/Postman.

---

## S01-01 — Docker Compose + Estrutura de Pastas

### Estrutura de pastas a criar

```
confex-ai/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── database.py
│   │   ├── auth.py
│   │   ├── models.py
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── common.py      ← StandardResponse genérico
│   │   │   ├── products.py
│   │   │   └── images.py
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── health.py
│   │   │   ├── auth.py
│   │   │   ├── products.py
│   │   │   └── images.py
│   │   ├── services/
│   │   │   └── __init__.py
│   │   └── migrations/
│   │       └── migrate_sprint_01.py
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   ├── test_health.py
│   │   ├── test_auth.py
│   │   ├── test_products.py
│   │   └── test_images.py
│   ├── uploads/              ← gitignored
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── main.jsx
│   │   ├── App.jsx
│   │   └── pages/
│   │       └── Home.jsx      ← placeholder "ConfexAI 🚀"
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   └── Dockerfile
├── docker-compose.yml
├── .env.example
├── .gitignore
└── docs/
    └── PRD_Sprint01_Fundacao.md
```

### docker-compose.yml

```yaml
version: "3.9"

services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: confexai
      POSTGRES_PASSWORD: confexai
      POSTGRES_DB: confexai_db
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  api:
    build: ./backend
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    volumes:
      - ./backend:/app
      - ./backend/uploads:/app/uploads
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql://confexai:confexai@db:5432/confexai_db
      DATABASE_TEST_URL: postgresql://confexai:confexai@db:5432/confexai_test_db
      SECRET_KEY: ${SECRET_KEY}
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
      GOOGLE_API_KEY: ${GOOGLE_API_KEY}
      KLING_ACCESS_KEY: ${KLING_ACCESS_KEY}
      KLING_SECRET_KEY: ${KLING_SECRET_KEY}
      UPLOAD_DIR: /app/uploads
      MAX_IMAGE_SIZE_MB: 20
    depends_on:
      - db

  frontend:
    build: ./frontend
    ports:
      - "5173:5173"
    volumes:
      - ./frontend:/app
      - /app/node_modules
    command: npm run dev -- --host

volumes:
  postgres_data:
```

### .env.example

```env
SECRET_KEY=troque-por-uma-chave-segura-de-32-chars
ANTHROPIC_API_KEY=
GOOGLE_API_KEY=
KLING_ACCESS_KEY=
KLING_SECRET_KEY=
```

### backend/Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
```

### backend/requirements.txt

```
fastapi==0.115.0
uvicorn[standard]==0.30.0
sqlalchemy==2.0.35
psycopg2-binary==2.9.9
pydantic==2.9.0
pydantic-settings==2.5.0
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.12
pillow==10.4.0
rembg==2.0.57
pytest==8.3.0
pytest-cov==5.0.0
httpx==0.27.0
```

### frontend/Dockerfile

```dockerfile
FROM node:20-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
EXPOSE 5173
```

---

## S01-02 — Modelos ORM + Migration

### backend/app/models.py

```python
import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Boolean, DateTime, Integer,
    Text, ForeignKey, Enum as SAEnum
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base
import enum


class JobType(str, enum.Enum):
    background_removal = "background_removal"
    protected_region_detection = "protected_region_detection"
    color_variation = "color_variation"
    background_alternative = "background_alternative"
    seo_description = "seo_description"
    video_ugc = "video_ugc"


class JobStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    done = "done"
    failed = "failed"
    pending_review = "pending_review"
    approved = "approved"
    rejected = "rejected"


class Product(Base):
    __tablename__ = "products"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    category = Column(String(50), nullable=False)
    fabric = Column(String(200), nullable=False)
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    images = relationship("ProductImage", back_populates="product")
    seo_descriptions = relationship("SEODescription", back_populates="product")


class ProductImage(Base):
    __tablename__ = "product_images"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    type = Column(String(50), nullable=False)  # original | color_variant | background | video
    original_url = Column(String(500), nullable=True)
    processed_url = Column(String(500), nullable=True)
    color_hex = Column(String(7), nullable=True)
    background_type = Column(String(50), nullable=True)
    platform_target = Column(String(30), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    product = relationship("Product", back_populates="images")
    jobs = relationship("GenerationJob", back_populates="product_image")


class GenerationJob(Base):
    __tablename__ = "generation_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_image_id = Column(UUID(as_uuid=True), ForeignKey("product_images.id"), nullable=False)
    type = Column(SAEnum(JobType), nullable=False)
    status = Column(SAEnum(JobStatus), default=JobStatus.pending, nullable=False)
    api_used = Column(String(30), nullable=True)   # anthropic | gemini | klingai | rembg
    cost_cents = Column(Integer, nullable=True)
    tokens_used = Column(Integer, nullable=True)
    result = Column(Text, nullable=True)           # JSON stringificado
    error_message = Column(Text, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    approved_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    product_image = relationship("ProductImage", back_populates="jobs")


class SEODescription(Base):
    __tablename__ = "seo_descriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    platform = Column(String(30), nullable=False)  # mercadolivre | shopee | shopify
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    tags = Column(Text, nullable=True)             # JSON array stringificado
    is_approved = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    product = relationship("Product", back_populates="seo_descriptions")
```

### backend/app/migrations/migrate_sprint_01.py

```python
"""
Migration Sprint 01 — Criação das tabelas base do ConfexAI.
Idempotente: seguro rodar múltiplas vezes.
"""
import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://confexai:confexai@localhost/confexai_db")
engine = create_engine(DATABASE_URL)


def table_exists(conn, table_name: str) -> bool:
    result = conn.execute(text(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
        "WHERE table_schema='public' AND table_name=:t)"
    ), {"t": table_name})
    return result.scalar()


def migrate():
    from app.database import Base
    from app import models  # garante que todos os modelos são importados

    with engine.begin() as conn:
        # Criar banco de teste se não existir
        conn.execute(text("COMMIT"))
        try:
            conn.execute(text("CREATE DATABASE confexai_test_db"))
            print("✅ Banco de teste confexai_test_db criado.")
        except Exception:
            print("✅ Banco de teste já existe.")

    Base.metadata.create_all(bind=engine)
    print("✅ Tabelas criadas: products, product_images, generation_jobs, seo_descriptions")


if __name__ == "__main__":
    migrate()
```

---

## S01-03 — Autenticação JWT

### backend/app/auth.py

```python
import os
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.database import get_db

SECRET_KEY = os.getenv("SECRET_KEY", "dev-insecure-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8  # 8 horas

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Token inválido.")
        return {"user_id": user_id, "email": payload.get("email")}
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido ou expirado.")
```

> **Nota MVP:** não há tabela de usuários no Sprint 01. O login aceita um usuário
> fixo definido via variável de ambiente (`ADMIN_EMAIL` / `ADMIN_PASSWORD_HASH`).
> Tabela `users` será criada no Sprint 02 quando multi-tenant for necessário.

### backend/app/api/auth.py

```python
import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.auth import verify_password, create_access_token, hash_password

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@confexai.local")
ADMIN_PASSWORD_HASH = os.getenv(
    "ADMIN_PASSWORD_HASH",
    hash_password("admin123")  # trocar em produção via variável de ambiente
)


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/login")
def login(payload: LoginRequest):
    if payload.email != ADMIN_EMAIL:
        raise HTTPException(status_code=401, detail="Credenciais inválidas.")
    if not verify_password(payload.password, ADMIN_PASSWORD_HASH):
        raise HTTPException(status_code=401, detail="Credenciais inválidas.")
    token = create_access_token({"sub": "admin", "email": payload.email})
    return {"data": {"access_token": token, "token_type": "bearer"}}
```

---

## S01-04 — CRUD de Produtos

### backend/app/schemas/common.py

```python
from typing import Generic, TypeVar
from pydantic import BaseModel

T = TypeVar("T")

class StandardResponse(BaseModel, Generic[T]):
    data: T
```

### backend/app/schemas/products.py

```python
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


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
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
```

### backend/app/api/products.py

```python
import logging
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.auth import get_current_user
from app.models import Product
from app.schemas.products import ProductCreate, ProductResponse
from app.schemas.common import StandardResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/products", tags=["products"])


@router.post("", response_model=StandardResponse[ProductResponse], status_code=201)
def create_product(
    payload: ProductCreate,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
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


@router.get("", response_model=StandardResponse[list[ProductResponse]])
def list_products(
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    products = db.query(Product).filter(Product.is_active == True).all()
    return StandardResponse(data=[ProductResponse.model_validate(p) for p in products])


@router.get("/{product_id}", response_model=StandardResponse[ProductResponse])
def get_product(
    product_id: UUID,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    product = db.query(Product).filter(
        Product.id == product_id,
        Product.is_active == True
    ).first()
    if not product:
        raise HTTPException(404, detail="Produto não encontrado.")
    return StandardResponse(data=ProductResponse.model_validate(product))


@router.delete("/{product_id}", response_model=StandardResponse[dict])
def delete_product(
    product_id: UUID,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    product = db.query(Product).filter(
        Product.id == product_id,
        Product.is_active == True
    ).first()
    if not product:
        raise HTTPException(404, detail="Produto não encontrado.")
    product.is_active = False  # soft delete
    db.commit()
    return StandardResponse(data={"deleted": True, "id": str(product_id)})
```

---

## S01-05 — Upload de Imagem

### backend/app/schemas/images.py

```python
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class ImageResponse(BaseModel):
    id: UUID
    product_id: UUID
    type: str
    original_url: str | None
    processed_url: str | None
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
```

### backend/app/api/images.py

```python
import os
import logging
from uuid import UUID
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from PIL import Image as PILImage
import io

from app.database import get_db
from app.auth import get_current_user
from app.models import Product, ProductImage
from app.schemas.images import ImageResponse
from app.schemas.common import StandardResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/products", tags=["images"])

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./uploads"))
MAX_IMAGE_SIZE_MB = int(os.getenv("MAX_IMAGE_SIZE_MB", 20))
ALLOWED_TYPES = {"image/jpeg", "image/png"}
MIN_RESOLUTION = 500


@router.post(
    "/{product_id}/images/upload",
    response_model=StandardResponse[ImageResponse],
    status_code=201,
)
async def upload_image(
    product_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    # Validar produto
    product = db.query(Product).filter(
        Product.id == product_id, Product.is_active == True
    ).first()
    if not product:
        raise HTTPException(404, detail="Produto não encontrado.")

    # Validar tipo de arquivo
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(422, detail="Formato inválido. Use JPG ou PNG.")

    # Ler conteúdo
    content = await file.read()

    # Validar tamanho
    size_mb = len(content) / (1024 * 1024)
    if size_mb > MAX_IMAGE_SIZE_MB:
        raise HTTPException(422, detail=f"Arquivo muito grande. Máximo: {MAX_IMAGE_SIZE_MB}MB.")

    # Validar resolução mínima
    try:
        img = PILImage.open(io.BytesIO(content))
        w, h = img.size
        if w < MIN_RESOLUTION or h < MIN_RESOLUTION:
            raise HTTPException(
                422,
                detail=f"Resolução mínima: {MIN_RESOLUTION}x{MIN_RESOLUTION}px. "
                       f"Recebido: {w}x{h}px."
            )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(422, detail="Arquivo de imagem inválido ou corrompido.")

    # Salvar arquivo
    product_dir = UPLOAD_DIR / str(product_id)
    product_dir.mkdir(parents=True, exist_ok=True)
    file_path = product_dir / f"original{Path(file.filename).suffix}"
    file_path.write_bytes(content)

    # Registrar no banco
    try:
        image = ProductImage(
            product_id=product_id,
            type="original",
            original_url=str(file_path),
        )
        db.add(image)
        db.commit()
        db.refresh(image)

        response_data = ImageResponse(
            id=image.id,
            product_id=image.product_id,
            type=image.type,
            original_url=image.original_url,
            processed_url=image.processed_url,
            status="uploaded",
            created_at=image.created_at,
        )
        return StandardResponse(data=response_data)
    except Exception as e:
        logger.error(f"Erro ao registrar imagem: {e}", exc_info=True)
        raise HTTPException(500, detail="Erro interno do servidor.")
```

### backend/app/api/health.py

```python
from fastapi import APIRouter

router = APIRouter(tags=["health"])

@router.get("/api/v1/health")
def health():
    return {"status": "ok", "service": "confexai-api"}
```

### backend/app/main.py

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import health, auth, products, images

app = FastAPI(title="ConfexAI API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(products.router)
app.include_router(images.router)
```

---

## S01-06 — Testes

### backend/tests/test_health.py

```python
def test_health_retorna_ok(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
```

### backend/tests/test_auth.py

```python
def test_login_com_credenciais_validas_retorna_token(client):
    response = client.post("/api/v1/auth/login", json={
        "email": "admin@confexai.local",
        "password": "admin123"
    })
    assert response.status_code == 200
    assert "access_token" in response.json()["data"]


def test_login_com_senha_errada_retorna_401(client):
    response = client.post("/api/v1/auth/login", json={
        "email": "admin@confexai.local",
        "password": "senhaerrada"
    })
    assert response.status_code == 401


def test_login_com_email_errado_retorna_401(client):
    response = client.post("/api/v1/auth/login", json={
        "email": "outro@email.com",
        "password": "admin123"
    })
    assert response.status_code == 401
```

### backend/tests/test_products.py

```python
import pytest

PAYLOAD_VALIDO = {
    "name": "TEST_PROD_Blusa Sprint01",
    "category": "blusa",
    "fabric": "viscose",
    "notes": "produto criado em teste automatizado"
}


def test_criar_produto_sem_token_retorna_401(client):
    response = client.post("/api/v1/products", json=PAYLOAD_VALIDO)
    assert response.status_code == 401


def test_criar_produto_valido_retorna_201(client, auth_headers):
    response = client.post("/api/v1/products", json=PAYLOAD_VALIDO, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["name"] == PAYLOAD_VALIDO["name"]
    assert "id" in data
    assert data["is_active"] is True


def test_criar_produto_nome_curto_retorna_422(client, auth_headers):
    payload = {**PAYLOAD_VALIDO, "name": "AB"}
    response = client.post("/api/v1/products", json=payload, headers=auth_headers)
    assert response.status_code == 422


def test_criar_produto_sem_category_retorna_422(client, auth_headers):
    payload = {k: v for k, v in PAYLOAD_VALIDO.items() if k != "category"}
    response = client.post("/api/v1/products", json=payload, headers=auth_headers)
    assert response.status_code == 422


def test_listar_produtos_retorna_lista(client, auth_headers, sample_product):
    response = client.get("/api/v1/products", headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json()["data"], list)


def test_buscar_produto_por_id(client, auth_headers, sample_product):
    response = client.get(f"/api/v1/products/{sample_product.id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["data"]["id"] == str(sample_product.id)


def test_buscar_produto_inexistente_retorna_404(client, auth_headers):
    response = client.get(
        "/api/v1/products/00000000-0000-0000-0000-000000000000",
        headers=auth_headers
    )
    assert response.status_code == 404


def test_deletar_produto_soft_delete(client, auth_headers, sample_product):
    response = client.delete(
        f"/api/v1/products/{sample_product.id}",
        headers=auth_headers
    )
    assert response.status_code == 200
    # Produto não aparece mais na listagem
    list_response = client.get("/api/v1/products", headers=auth_headers)
    ids = [p["id"] for p in list_response.json()["data"]]
    assert str(sample_product.id) not in ids
```

### backend/tests/test_images.py

```python
import io
from PIL import Image as PILImage


def _make_jpg(width=600, height=600) -> bytes:
    img = PILImage.new("RGB", (width, height), color=(200, 200, 200))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def test_upload_jpg_valido_retorna_201(client, auth_headers, sample_product):
    response = client.post(
        f"/api/v1/products/{sample_product.id}/images/upload",
        files={"file": ("peça.jpg", _make_jpg(), "image/jpeg")},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["type"] == "original"
    assert data["original_url"] is not None


def test_upload_sem_token_retorna_401(client, sample_product):
    response = client.post(
        f"/api/v1/products/{sample_product.id}/images/upload",
        files={"file": ("peça.jpg", _make_jpg(), "image/jpeg")},
    )
    assert response.status_code == 401


def test_upload_produto_inexistente_retorna_404(client, auth_headers):
    response = client.post(
        "/api/v1/products/00000000-0000-0000-0000-000000000000/images/upload",
        files={"file": ("peça.jpg", _make_jpg(), "image/jpeg")},
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_upload_pdf_retorna_422(client, auth_headers, sample_product):
    response = client.post(
        f"/api/v1/products/{sample_product.id}/images/upload",
        files={"file": ("doc.pdf", b"%PDF-content", "application/pdf")},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_upload_resolucao_abaixo_do_minimo_retorna_422(client, auth_headers, sample_product):
    small_img = _make_jpg(width=200, height=200)
    response = client.post(
        f"/api/v1/products/{sample_product.id}/images/upload",
        files={"file": ("pequena.jpg", small_img, "image/jpeg")},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_upload_arquivo_muito_grande_retorna_422(client, auth_headers, sample_product):
    big_content = b"x" * (21 * 1024 * 1024)  # 21MB
    response = client.post(
        f"/api/v1/products/{sample_product.id}/images/upload",
        files={"file": ("grande.jpg", big_content, "image/jpeg")},
        headers=auth_headers,
    )
    assert response.status_code == 422
```

---

## Ordem de Execução

```
S01-01 → S01-02 → S01-03 → S01-04 → S01-05 → S01-06
```

Cada item depende do anterior. Não paralelizar.

---

## Commits Atômicos

```
devops(infra): scaffold project structure and Docker Compose [S01-01]
feat(db): add ORM models and sprint 01 migration [S01-02]
feat(auth): add JWT login with static admin credentials [S01-03]
feat(products): add create, list, get, soft-delete endpoints [S01-04]
feat(images): add image upload endpoint with validation [S01-05]
test(sprint01): add full test suite for all Sprint 01 endpoints [S01-06]
```

---

## Critérios de Aceite

- [ ] `docker-compose up -d` sobe sem erros
- [ ] `python migrate_sprint_01.py` cria as 4 tabelas + banco de teste
- [ ] `GET /api/v1/health` retorna `{"status": "ok"}`
- [ ] `POST /api/v1/auth/login` retorna JWT válido
- [ ] `POST /api/v1/products` cria produto (com token)
- [ ] `POST /api/v1/products/{id}/images/upload` aceita JPG ≥ 500px e recusa inválidos
- [ ] `pytest backend/tests/ -v` → **todos os testes passam, 0 falhas**
- [ ] Frontend sobe em `localhost:5173` com placeholder "ConfexAI 🚀"
