---
name: confexai-testing-standards
description: >
  Padrões de testes obrigatórios do ConfexAI. Use esta SKILL sempre que for
  escrever, revisar ou planejar testes no projeto ConfexAI. Também use ao
  adicionar novas rotas, corrigir bugs, ou criar features — todo código novo
  exige testes correspondentes. Define: banco de teste correto, fixtures
  obrigatórias, estrutura por módulo, mocks de APIs externas, e os cenários
  mínimos que todo endpoint deve ter coberto. Nunca escreva testes no ConfexAI
  sem consultar esta SKILL primeiro.
---

# ConfexAI — Padrões de Testes

## Filosofia

**Custo de API não pode entrar em testes.**  
Toda chamada a Anthropic, Gemini e KlingAI deve ser mockada.
Nenhum teste deve fazer chamada real a APIs externas.

**Banco de teste separado, sempre.**  
Nunca rodar testes contra o banco de produção ou desenvolvimento.

---

## Configuração Base

### Banco de Teste
```
Nome: confexai_test_db
Host: localhost (ou container `db` no Docker)
```

### Prefixos de Cleanup (dados criados em testes)
```
Produtos:   TEST_PROD_*
Imagens:    TEST_IMG_*
Jobs:       TEST_JOB_*
Usuários:   testuser_*
```

### Arquivo de configuração
```python
# backend/tests/conftest.py

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from app.main import app
from app.database import Base, get_db

TEST_DATABASE_URL = "postgresql://user:pass@localhost/confexai_test_db"

engine = create_engine(TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(bind=engine)

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def db():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()

@pytest.fixture
def client(db):
    def override_get_db():
        yield db
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

@pytest.fixture
def auth_headers(client):
    """Token JWT válido para testes."""
    response = client.post("/api/v1/auth/login", json={
        "email": "testuser_admin@confexai.test",
        "password": "TestPass123!"
    })
    token = response.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def mock_anthropic():
    """Mock do cliente Anthropic para testes."""
    with patch("app.services.seo_generator.anthropic.Anthropic") as mock:
        instance = MagicMock()
        mock.return_value = instance
        yield instance

@pytest.fixture
def mock_gemini():
    """Mock do cliente Gemini para testes."""
    with patch("app.services.color_variation.genai") as mock:
        yield mock

@pytest.fixture
def mock_rembg():
    """Mock do rembg para testes."""
    with patch("app.services.background_removal.remove") as mock:
        # Retorna PNG mínimo válido
        mock.return_value = _minimal_png_bytes()
        yield mock

@pytest.fixture
def sample_product(db):
    """Produto de teste padrão."""
    from app.models import Product
    product = Product(
        name="TEST_PROD_Blusa Teste",
        category="blusa",
        fabric="viscose",
        notes="produto para testes automatizados"
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    yield product
    db.delete(product)
    db.commit()

@pytest.fixture
def sample_image_bytes():
    """Imagem JPG mínima válida para upload em testes."""
    return _minimal_jpg_bytes()

def _minimal_png_bytes() -> bytes:
    """Gera PNG mínimo válido (1x1 pixel transparente)."""
    from PIL import Image
    import io
    img = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def _minimal_jpg_bytes() -> bytes:
    """Gera JPG mínimo válido (500x500 branco)."""
    from PIL import Image
    import io
    img = Image.new("RGB", (500, 500), (255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()
```

---

## Cenários Obrigatórios por Endpoint

Todo endpoint novo deve ter NO MÍNIMO estes cenários:

```python
# Modelo de teste obrigatório para cada router

def test_{recurso}_sem_token_retorna_401(client):
    response = client.get("/api/v1/{recurso}")
    assert response.status_code == 401

def test_{recurso}_com_token_valido_retorna_200(client, auth_headers):
    response = client.get("/api/v1/{recurso}", headers=auth_headers)
    assert response.status_code == 200

def test_criar_{recurso}_com_payload_valido_retorna_201(client, auth_headers):
    response = client.post("/api/v1/{recurso}", json={...}, headers=auth_headers)
    assert response.status_code == 201
    assert "id" in response.json()["data"]

def test_criar_{recurso}_com_payload_invalido_retorna_422(client, auth_headers):
    response = client.post("/api/v1/{recurso}", json={}, headers=auth_headers)
    assert response.status_code == 422

def test_{recurso}_nao_encontrado_retorna_404(client, auth_headers):
    response = client.get("/api/v1/{recurso}/uuid-inexistente", headers=auth_headers)
    assert response.status_code == 404
```

---

## Testes por Módulo

### Módulo: Produtos

```python
# backend/tests/test_products.py

class TestProductCreate:
    def test_sem_token_retorna_401(self, client):
        ...

    def test_com_payload_valido_retorna_201(self, client, auth_headers):
        payload = {
            "name": "TEST_PROD_Blusa Unitária",
            "category": "blusa",
            "fabric": "algodão",
        }
        response = client.post("/api/v1/products", json=payload, headers=auth_headers)
        assert response.status_code == 201
        data = response.json()["data"]
        assert data["name"] == payload["name"]
        assert "id" in data

    def test_nome_muito_curto_retorna_422(self, client, auth_headers):
        payload = {"name": "AB", "category": "blusa", "fabric": "algodão"}
        response = client.post("/api/v1/products", json=payload, headers=auth_headers)
        assert response.status_code == 422

    def test_produto_deletado_soft_delete(self, client, auth_headers, sample_product):
        response = client.delete(
            f"/api/v1/products/{sample_product.id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        # Produto ainda existe no banco, só is_active=False
        from app.models import Product
        # verificar via db fixture
```

### Módulo: Upload de Imagens

```python
# backend/tests/test_images.py

class TestImageUpload:
    def test_upload_jpg_valido_retorna_201(
        self, client, auth_headers, sample_product, sample_image_bytes
    ):
        response = client.post(
            f"/api/v1/products/{sample_product.id}/images/upload",
            files={"file": ("test.jpg", sample_image_bytes, "image/jpeg")},
            headers=auth_headers,
        )
        assert response.status_code == 201
        assert response.json()["data"]["type"] == "original"

    def test_upload_arquivo_muito_grande_retorna_422(
        self, client, auth_headers, sample_product
    ):
        big_image = b"x" * (21 * 1024 * 1024)  # 21MB
        response = client.post(
            f"/api/v1/products/{sample_product.id}/images/upload",
            files={"file": ("big.jpg", big_image, "image/jpeg")},
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_upload_formato_invalido_retorna_422(
        self, client, auth_headers, sample_product
    ):
        response = client.post(
            f"/api/v1/products/{sample_product.id}/images/upload",
            files={"file": ("doc.pdf", b"pdf content", "application/pdf")},
            headers=auth_headers,
        )
        assert response.status_code == 422
```

### Módulo: Jobs de Geração (com mocks de API)

```python
# backend/tests/test_jobs.py

class TestColorVariationJob:
    def test_criar_job_cor_retorna_202(
        self, client, auth_headers, sample_product, mock_gemini
    ):
        # Mock Gemini retorna imagem válida
        mock_gemini.ImageGenerationModel.return_value.edit_image.return_value = \
            MagicMock(images=[MagicMock(_image_bytes=_minimal_png_bytes())])
        
        payload = {
            "product_image_id": str(sample_product.id),
            "type": "color_variation",
            "params": {
                "target_colors": ["#FF5733"],
                "protected_regions": []
            }
        }
        response = client.post("/api/v1/jobs", json=payload, headers=auth_headers)
        assert response.status_code == 202
        assert response.json()["data"]["status"] == "pending"

    def test_polling_job_retorna_status(self, client, auth_headers):
        ...

    def test_job_com_api_falha_marca_status_failed(
        self, client, auth_headers, mock_gemini
    ):
        mock_gemini.ImageGenerationModel.return_value.edit_image.side_effect = \
            Exception("API timeout")
        ...

class TestSEOGeneration:
    def test_gerar_descricao_ml_retorna_202(
        self, client, auth_headers, sample_product, mock_anthropic
    ):
        # Mock Claude retorna análise válida
        mock_anthropic.messages.create.return_value = MagicMock(
            content=[MagicMock(text='{"garment_type":"blusa","gender_target":"feminino",...}')]
        )
        ...

    def test_descricao_ml_titulo_nao_excede_60_chars(self, ...):
        ...
```

### Módulo: Aprovação

```python
# backend/tests/test_approval.py

class TestJobApproval:
    def test_aprovar_job_done_retorna_200(self, ...):
        ...

    def test_aprovar_job_pending_retorna_409(self, ...):
        # Só pode aprovar jobs com status "done"
        ...

    def test_rejeitar_job_registra_motivo(self, ...):
        ...
```

---

## Meta de Cobertura

```
Linhas de teste >= linhas de código de produção adicionadas por sprint
Cobertura mínima: 80% dos endpoints cobertos com cenários happy + error path
```

---

## Rodar Testes

```bash
# Dentro do container
docker-compose exec api python -m pytest backend/tests/ -v

# Com cobertura
docker-compose exec api python -m pytest backend/tests/ -v --cov=app --cov-report=term-missing

# Módulo específico
docker-compose exec api python -m pytest backend/tests/test_products.py -v

# Target de aprovação
# NNN passed, 0 failed
```

**Nunca commitar com testes falhando.**

---

## Severidade de Falhas de Teste

| 🔴 Crítico | Endpoint retorna 500 inesperado, auth bypass, dados corrompidos |
|---|---|
| 🟡 Médio | Validação incorreta, status code errado, campo faltando |
| 🟢 Baixo | Mensagem de erro imprecisa, campo extra desnecessário |

Falhas 🔴 bloqueiam o merge.
