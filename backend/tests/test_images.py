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
        files={"file": ("peca.jpg", _make_jpg(), "image/jpeg")},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["type"] == "original"
    assert data["original_url"] is not None


def test_upload_sem_token_retorna_401(client, sample_product):
    response = client.post(
        f"/api/v1/products/{sample_product.id}/images/upload",
        files={"file": ("peca.jpg", _make_jpg(), "image/jpeg")},
    )
    assert response.status_code == 401 or response.status_code == 403


def test_upload_produto_inexistente_retorna_404(client, auth_headers):
    response = client.post(
        "/api/v1/products/00000000-0000-0000-0000-000000000000/images/upload",
        files={"file": ("peca.jpg", _make_jpg(), "image/jpeg")},
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
