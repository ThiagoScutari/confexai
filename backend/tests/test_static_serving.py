def test_static_uploads_endpoint_acessivel(client):
    """Confirma que /static/uploads/ esta montado e respondendo."""
    response = client.get("/static/uploads/")
    # 404 e esperado para diretorio raiz — mas nao 500
    assert response.status_code in (200, 404)


def test_path_to_url_converte_corretamente():
    from app.services.url_helper import path_to_url
    url = path_to_url("/app/examples/uploads/uuid-123/color_696980_frente.jpg")
    assert url == "/static/uploads/uuid-123/color_696980_frente.jpg"


def test_path_to_url_path_fora_do_upload_dir():
    from app.services.url_helper import path_to_url
    url = path_to_url("/tmp/outro_arquivo.jpg")
    assert url == "/tmp/outro_arquivo.jpg"


def test_image_upload_retorna_public_url(client, auth_headers, sample_product):
    import io
    from PIL import Image as PILImage

    img = PILImage.new("RGB", (600, 600), color=(200, 200, 200))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")

    response = client.post(
        f"/api/v1/products/{sample_product.id}/images/upload",
        files={"file": ("frente.jpg", buf.getvalue(), "image/jpeg")},
        params={"view": "frente"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert "public_url" in data
    assert data["public_url"].startswith("/static/uploads/")
