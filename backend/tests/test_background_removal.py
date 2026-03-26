from unittest.mock import patch, MagicMock
import io
from PIL import Image


def _png_transparent() -> bytes:
    img = Image.new("RGBA", (600, 600), (0, 0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _png_opaque() -> bytes:
    img = Image.new("RGBA", (600, 600), (200, 150, 100, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_remover_fundo_imagem_ja_transparente_retorna_skip(
    client, auth_headers, sample_product
):
    # Upload imagem transparente
    upload = client.post(
        f"/api/v1/products/{sample_product.id}/images/upload",
        files={"file": ("frente.png", _png_transparent(), "image/png")},
        params={"view": "frente"},
        headers=auth_headers,
    )
    assert upload.status_code == 201
    image_id = upload.json()["data"]["id"]

    response = client.post(
        f"/api/v1/products/{sample_product.id}/images/{image_id}/remove-background",
        headers=auth_headers,
    )
    assert response.status_code == 202
    data = response.json()["data"]
    assert data["skipped"] is True
    assert data["status"] == "done"


def test_remover_fundo_imagem_opaca_chama_rembg(
    client, auth_headers, sample_product
):
    upload = client.post(
        f"/api/v1/products/{sample_product.id}/images/upload",
        files={"file": ("frente.png", _png_opaque(), "image/png")},
        headers=auth_headers,
    )
    image_id = upload.json()["data"]["id"]

    with patch("app.services.background_removal.remove_background") as mock_rembg:
        mock_rembg.return_value = (_png_transparent(), 0.92)
        response = client.post(
            f"/api/v1/products/{sample_product.id}/images/{image_id}/remove-background",
            headers=auth_headers,
        )
    assert response.status_code == 202
    assert response.json()["data"]["confidence"] == 0.92


def test_upload_com_view_registra_campo(client, auth_headers, sample_product):
    response = client.post(
        f"/api/v1/products/{sample_product.id}/images/upload",
        files={"file": ("costas.png", _png_transparent(), "image/png")},
        params={"view": "costas"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    assert response.json()["data"]["view"] == "costas"


def test_upload_view_invalido_retorna_422(client, auth_headers, sample_product):
    response = client.post(
        f"/api/v1/products/{sample_product.id}/images/upload",
        files={"file": ("x.png", _png_transparent(), "image/png")},
        params={"view": "diagonal"},
        headers=auth_headers,
    )
    assert response.status_code == 422
