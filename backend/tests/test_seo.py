import json
import pytest
from unittest.mock import patch, MagicMock


MOCK_ANALYSIS = {
    "garment_type": "blusa",
    "gender_target": "feminino",
    "modeling": "regular",
    "fabric_apparent": "viscose",
    "main_color": "azul",
    "has_print": False,
    "print_type": None,
    "has_embroidery": False,
    "embroidery_description": None,
    "notable_details": [],
    "style": "casual",
    "season": "atemporal",
    "wash_care_likely": "lavar à máquina fria",
}

MOCK_ML_RESULT = {
    "title": "Blusa Feminina Viscose Casual – Tam P ao GG",
    "description": "Blusa feminina em viscose leve e macia. Modelagem regular, ideal para o dia a dia.",
    "keywords": ["blusa feminina", "viscose", "casual"],
    "title_char_count": 43,
    "seo_score_rationale": "Inclui tipo, material e público-alvo.",
}

MOCK_SHOPEE_RESULT = {
    "title": "Blusa Feminina Viscose Casual Moda Feminina Confortável",
    "description": "✨ BLUSA FEMININA\n\n👗 Tecido viscose macio\n\n🧺 Lavar à máquina fria",
    "tags": [f"tag{i}" for i in range(15)],
    "title_char_count": 54,
}

MOCK_SHOPIFY_RESULT = {
    "title": "Blusa Casual – Viscose Premium",
    "description_html": "<p>Uma blusa elegante para o dia a dia.</p>",
    "meta_description": "Blusa feminina casual em viscose, modelagem regular. Conforto e estilo para o dia a dia.",
    "meta_keywords": ["blusa", "viscose", "feminina"],
}


def _mock_seo_service():
    mock = MagicMock()
    mock.analyze_garment.return_value = (MOCK_ANALYSIS, 500)
    mock.generate_for_platform.side_effect = lambda garment_analysis, colors, platform: {
        "mercadolivre": (MOCK_ML_RESULT, 300, []),
        "shopee": (MOCK_SHOPEE_RESULT, 400, []),
        "shopify": (MOCK_SHOPIFY_RESULT, 350, []),
    }[platform]
    return mock


def test_gerar_seo_sem_token_retorna_401(client, sample_product):
    response = client.post(f"/api/v1/products/{sample_product.id}/seo", json={})
    assert response.status_code == 403


def test_gerar_seo_produto_inexistente_retorna_404(client, auth_headers):
    with patch("app.api.products.SEOGeneratorService") as MockSvc:
        MockSvc.return_value = _mock_seo_service()
        response = client.post(
            "/api/v1/products/00000000-0000-0000-0000-000000000000/seo",
            json={"platforms": ["mercadolivre"]},
            headers=auth_headers,
        )
    assert response.status_code == 404


def test_gerar_seo_produto_sem_imagem_retorna_422(client, auth_headers, sample_product):
    with patch("app.api.products.SEOGeneratorService") as MockSvc:
        MockSvc.return_value = _mock_seo_service()
        response = client.post(
            f"/api/v1/products/{sample_product.id}/seo",
            json={"platforms": ["mercadolivre"]},
            headers=auth_headers,
        )
    assert response.status_code == 422


def test_gerar_seo_retorna_202_com_resultados(
    client, auth_headers, sample_product, sample_image_uploaded
):
    with patch("app.api.products.SEOGeneratorService") as MockSvc:
        MockSvc.return_value = _mock_seo_service()
        response = client.post(
            f"/api/v1/products/{sample_product.id}/seo",
            json={"platforms": ["mercadolivre", "shopee"], "colors": ["#696980"]},
            headers=auth_headers,
        )
    assert response.status_code == 202
    data = response.json()["data"]
    assert "garment_analysis" in data
    assert len(data["results"]) == 2
    assert data["results"][0]["platform"] in ["mercadolivre", "shopee"]


def test_listar_seo_sem_token_retorna_401(client, sample_product):
    response = client.get(f"/api/v1/products/{sample_product.id}/seo")
    assert response.status_code == 403


def test_listar_seo_retorna_200(client, auth_headers, sample_product):
    response = client.get(
        f"/api/v1/products/{sample_product.id}/seo",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert isinstance(response.json()["data"], list)


def test_gerar_seo_salva_no_banco(
    client, auth_headers, sample_product, sample_image_uploaded, db
):
    from app.models import SEODescription
    with patch("app.api.products.SEOGeneratorService") as MockSvc:
        MockSvc.return_value = _mock_seo_service()
        client.post(
            f"/api/v1/products/{sample_product.id}/seo",
            json={"platforms": ["mercadolivre"], "colors": []},
            headers=auth_headers,
        )
    saved = db.query(SEODescription).filter(
        SEODescription.product_id == sample_product.id,
        SEODescription.platform == "mercadolivre",
    ).first()
    assert saved is not None
    assert saved.title == MOCK_ML_RESULT["title"]


def test_gerar_seo_substitui_descricao_existente(
    client, auth_headers, sample_product, sample_image_uploaded, db
):
    """Gerar duas vezes deve substituir, não duplicar."""
    from app.models import SEODescription
    with patch("app.api.products.SEOGeneratorService") as MockSvc:
        MockSvc.return_value = _mock_seo_service()
        client.post(
            f"/api/v1/products/{sample_product.id}/seo",
            json={"platforms": ["shopee"], "colors": []},
            headers=auth_headers,
        )
        client.post(
            f"/api/v1/products/{sample_product.id}/seo",
            json={"platforms": ["shopee"], "colors": []},
            headers=auth_headers,
        )
    count = db.query(SEODescription).filter(
        SEODescription.product_id == sample_product.id,
        SEODescription.platform == "shopee",
    ).count()
    assert count == 1  # não deve duplicar
