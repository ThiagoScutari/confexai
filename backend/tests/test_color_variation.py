from unittest.mock import patch, MagicMock
import io
from PIL import Image


def _sample_png() -> bytes:
    img = Image.new("RGBA", (600, 600), (150, 100, 80, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


MOCK_COLOR_RESULT = {
    "png_url": "/tmp/color_696980_frente.png",
    "jpg_url": "/tmp/color_696980_frente.jpg",
    "resolution": "600x600",
    "cost_cents": 3,
}


def test_gerar_variacao_cor_retorna_202(client, auth_headers, sample_product):
    upload = client.post(
        f"/api/v1/products/{sample_product.id}/images/upload",
        files={"file": ("frente.png", _sample_png(), "image/png")},
        params={"view": "frente"},
        headers=auth_headers,
    )
    image_id = upload.json()["data"]["id"]

    with patch("app.services.color_variation.apply_color_variation") as mock_cv:
        mock_cv.return_value = MOCK_COLOR_RESULT
        response = client.post(
            "/api/v1/jobs/color-variation",
            json={
                "product_image_id": image_id,
                "target_colors": ["#696980"],
                "protected_regions": [],
            },
            headers=auth_headers,
        )

    assert response.status_code == 202
    results = response.json()["data"]["results"]
    assert len(results) == 1
    assert results[0]["color_hex"] == "#696980"
    assert results[0]["status"] == "pending_review"


def test_gerar_variacao_multiplas_cores(client, auth_headers, sample_product):
    upload = client.post(
        f"/api/v1/products/{sample_product.id}/images/upload",
        files={"file": ("frente.png", _sample_png(), "image/png")},
        headers=auth_headers,
    )
    image_id = upload.json()["data"]["id"]

    with patch("app.services.color_variation.apply_color_variation") as mock_cv:
        mock_cv.return_value = {**MOCK_COLOR_RESULT, "cost_cents": 3}
        response = client.post(
            "/api/v1/jobs/color-variation",
            json={
                "product_image_id": image_id,
                "target_colors": ["#696980", "#978b7b", "#9e987d"],
                "protected_regions": [],
            },
            headers=auth_headers,
        )

    assert response.status_code == 202
    data = response.json()["data"]
    assert len(data["results"]) == 3
    assert data["total_cost_cents"] == 9


def test_gerar_variacao_sem_token_retorna_401(client):
    response = client.post("/api/v1/jobs/color-variation", json={})
    assert response.status_code == 401 or response.status_code == 403
