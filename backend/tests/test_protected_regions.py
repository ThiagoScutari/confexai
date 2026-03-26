from unittest.mock import patch, MagicMock
import json
import io
from PIL import Image


def _sample_png() -> bytes:
    img = Image.new("RGBA", (600, 600), (150, 100, 80, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


MOCK_RESULT_SEM_REGIOES = {
    "has_protected_regions": False,
    "protected_regions": [],
    "tokens_used": 320,
}

MOCK_RESULT_COM_REGIOES = {
    "has_protected_regions": True,
    "protected_regions": [{
        "type": "estampa",
        "description": "estampa floral no centro",
        "bbox": {"x": 100, "y": 80, "width": 200, "height": 180},
        "confidence": 0.91,
    }],
    "tokens_used": 480,
}


def test_detectar_regioes_peca_lisa_retorna_false(client, auth_headers, sample_product):
    upload = client.post(
        f"/api/v1/products/{sample_product.id}/images/upload",
        files={"file": ("frente.png", _sample_png(), "image/png")},
        headers=auth_headers,
    )
    image_id = upload.json()["data"]["id"]

    with patch("app.services.protected_regions.detect_protected_regions") as mock_detect:
        mock_detect.return_value = MOCK_RESULT_SEM_REGIOES
        response = client.post(
            "/api/v1/jobs/detect-protected-regions",
            json={"product_image_id": image_id},
            headers=auth_headers,
        )

    assert response.status_code == 202
    data = response.json()["data"]
    assert data["has_protected_regions"] is False
    assert data["regions_count"] == 0
    assert data["cost_cents"] >= 0


def test_detectar_regioes_peca_com_estampa_retorna_true(client, auth_headers, sample_product):
    upload = client.post(
        f"/api/v1/products/{sample_product.id}/images/upload",
        files={"file": ("frente.png", _sample_png(), "image/png")},
        headers=auth_headers,
    )
    image_id = upload.json()["data"]["id"]

    with patch("app.services.protected_regions.detect_protected_regions") as mock_detect:
        mock_detect.return_value = MOCK_RESULT_COM_REGIOES
        response = client.post(
            "/api/v1/jobs/detect-protected-regions",
            json={"product_image_id": image_id},
            headers=auth_headers,
        )

    assert response.status_code == 202
    assert response.json()["data"]["has_protected_regions"] is True
    assert response.json()["data"]["regions_count"] == 1


def test_detectar_regioes_sem_image_id_retorna_422(client, auth_headers):
    response = client.post(
        "/api/v1/jobs/detect-protected-regions",
        json={},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_detectar_regioes_sem_token_retorna_401(client):
    response = client.post("/api/v1/jobs/detect-protected-regions", json={})
    assert response.status_code == 401 or response.status_code == 403
