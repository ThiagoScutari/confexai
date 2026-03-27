import pytest
from unittest.mock import patch, MagicMock
import time

from app.api.products import _seo_rate_limit


@pytest.fixture(autouse=True)
def clear_rate_limit():
    """Limpa o rate limit entre testes para evitar interferência."""
    _seo_rate_limit.clear()
    yield
    _seo_rate_limit.clear()


def _mock_seo():
    mock = MagicMock()
    mock.analyze_garment.return_value = ({"garment_type": "blusa"}, 100)
    mock.generate_for_platform.return_value = (
        {
            "title": "Blusa Teste",
            "description": "Descrição teste",
            "keywords": ["blusa"],
            "title_char_count": 11,
            "seo_score_rationale": "ok",
        },
        100,
        [],
    )
    return mock


def test_segunda_geracao_imediata_retorna_429(
    client, auth_headers, sample_product, sample_image_uploaded
):
    """Duas gerações seguidas para o mesmo produto devem bloquear a segunda."""
    with patch("app.api.products.SEOGeneratorService") as MockSvc:
        MockSvc.return_value = _mock_seo()
        # Primeira geração — deve passar
        r1 = client.post(
            f"/api/v1/products/{sample_product.id}/seo",
            json={"platforms": ["mercadolivre"]},
            headers=auth_headers,
        )
        assert r1.status_code == 202

        # Segunda geração imediata — deve ser bloqueada
        r2 = client.post(
            f"/api/v1/products/{sample_product.id}/seo",
            json={"platforms": ["mercadolivre"]},
            headers=auth_headers,
        )
        assert r2.status_code == 429
        assert "Aguarde" in r2.json()["detail"]


def test_produtos_diferentes_nao_interferem(
    client, auth_headers, sample_product, sample_image_uploaded, db
):
    """Rate limit é por produto — produtos diferentes não interferem."""
    from app.models import Product, ProductImage
    from pathlib import Path
    import os
    import io
    from PIL import Image as PILImage

    # Criar segundo produto com imagem
    p2 = Product(name="TEST_PROD_Segundo", category="calça", fabric="algodão")
    db.add(p2)
    db.commit()

    upload_dir = Path(os.getenv("UPLOAD_DIR", "/app/examples/uploads"))
    p2_dir = upload_dir / str(p2.id)
    p2_dir.mkdir(parents=True, exist_ok=True)
    img_path = p2_dir / "original_frente.png"
    img = PILImage.new("RGBA", (600, 600), (100, 100, 100, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    img_path.write_bytes(buf.getvalue())

    img2 = ProductImage(
        product_id=p2.id, type="original", view="frente",
        original_url=str(img_path)
    )
    db.add(img2)
    db.commit()

    with patch("app.api.products.SEOGeneratorService") as MockSvc:
        MockSvc.return_value = _mock_seo()
        # Gerar para produto 1
        r1 = client.post(
            f"/api/v1/products/{sample_product.id}/seo",
            json={"platforms": ["mercadolivre"]},
            headers=auth_headers,
        )
        assert r1.status_code == 202

        # Gerar para produto 2 — deve passar (produto diferente)
        r2 = client.post(
            f"/api/v1/products/{p2.id}/seo",
            json={"platforms": ["mercadolivre"]},
            headers=auth_headers,
        )
        assert r2.status_code == 202

    # Cleanup — deletar SEO descriptions antes do produto
    from app.models import SEODescription
    db.query(SEODescription).filter(SEODescription.product_id == p2.id).delete()
    db.delete(img2)
    db.delete(p2)
    db.commit()
    if img_path.exists():
        img_path.unlink()


def test_updated_at_presente_na_resposta(
    client, auth_headers, sample_product, sample_image_uploaded
):
    """GET /seo deve retornar updated_at em cada descrição."""
    with patch("app.api.products.SEOGeneratorService") as MockSvc:
        MockSvc.return_value = _mock_seo()
        client.post(
            f"/api/v1/products/{sample_product.id}/seo",
            json={"platforms": ["mercadolivre"]},
            headers=auth_headers,
        )

    response = client.get(
        f"/api/v1/products/{sample_product.id}/seo",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) > 0
    assert "updated_at" in data[0], "Campo updated_at ausente na resposta"
