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
    from app.models import ProductImage, GenerationJob, SEODescription
    # Clean up SEO descriptions linked to this product
    db.query(SEODescription).filter(SEODescription.product_id == product.id).delete()
    # Clean up jobs linked to images of this product
    image_ids = [img.id for img in db.query(ProductImage).filter(ProductImage.product_id == product.id).all()]
    if image_ids:
        db.query(GenerationJob).filter(GenerationJob.product_image_id.in_(image_ids)).delete(synchronize_session=False)
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


@pytest.fixture
def sample_image_uploaded(db, sample_product):
    """ProductImage com arquivo PNG real no disco para testes de SEO."""
    import io
    from PIL import Image as PILImage
    from pathlib import Path

    upload_dir = Path(os.getenv("UPLOAD_DIR", "/app/examples/uploads"))
    product_dir = upload_dir / str(sample_product.id)
    product_dir.mkdir(parents=True, exist_ok=True)
    img_path = product_dir / "original_frente.png"

    img = PILImage.new("RGBA", (600, 600), (150, 100, 80, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    img_path.write_bytes(buf.getvalue())

    from app.models import ProductImage
    image = ProductImage(
        product_id=sample_product.id,
        type="original",
        view="frente",
        original_url=str(img_path),
    )
    db.add(image)
    db.commit()
    db.refresh(image)
    yield image

    db.delete(image)
    db.commit()
    if img_path.exists():
        img_path.unlink()


@pytest.fixture
def sample_job_pending_review(db, sample_product):
    """Job em status pending_review para testes de aprovacao."""
    from app.models import ProductImage, GenerationJob, JobType, JobStatus
    image = ProductImage(
        product_id=sample_product.id,
        type="color_variant",
        original_url="/tmp/test_original.png",
        processed_url="/tmp/test_processed.png",
    )
    db.add(image)
    db.commit()
    db.refresh(image)
    job = GenerationJob(
        product_image_id=image.id,
        type=JobType.color_variation,
        status=JobStatus.pending_review,
        api_used="gemini",
        cost_cents=3,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    yield job
    db.delete(job)
    db.delete(image)
    db.commit()


@pytest.fixture
def sample_job_done(db, sample_product):
    """Job em status done para testes de aprovacao."""
    from app.models import ProductImage, GenerationJob, JobType, JobStatus
    image = ProductImage(
        product_id=sample_product.id,
        type="original",
        original_url="/tmp/test_original_done.png",
    )
    db.add(image)
    db.commit()
    db.refresh(image)
    job = GenerationJob(
        product_image_id=image.id,
        type=JobType.background_removal,
        status=JobStatus.done,
        api_used="rembg",
        cost_cents=0,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    yield job
    db.delete(job)
    db.delete(image)
    db.commit()
