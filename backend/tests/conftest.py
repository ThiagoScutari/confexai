import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from app.main import app
from app.database import Base, get_db

TEST_DATABASE_URL = os.getenv(
    "DATABASE_TEST_URL",
    "postgresql://confexai:confexai@db:5432/confexai_test_db"
)

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
    """Token JWT valido para testes."""
    response = client.post("/api/v1/auth/login", json={
        "email": "admin@confexai.local",
        "password": "admin123"
    })
    token = response.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sample_product(db):
    """Produto de teste padrao."""
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
    from app.models import ProductImage
    db.query(ProductImage).filter(ProductImage.product_id == product.id).delete()
    db.delete(product)
    db.commit()


@pytest.fixture
def sample_image_bytes():
    """Imagem JPG minima valida para upload em testes."""
    return _minimal_jpg_bytes()


def _minimal_png_bytes() -> bytes:
    """Gera PNG minimo valido (1x1 pixel transparente)."""
    from PIL import Image
    import io
    img = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _minimal_jpg_bytes() -> bytes:
    """Gera JPG minimo valido (600x600 cinza)."""
    from PIL import Image
    import io
    img = Image.new("RGB", (600, 600), (200, 200, 200))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()
