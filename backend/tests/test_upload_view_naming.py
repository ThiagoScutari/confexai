import io
from PIL import Image as PILImage
from pathlib import Path


def _make_png(width=600, height=600) -> bytes:
    img = PILImage.new("RGBA", (width, height), (150, 100, 80, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_upload_frente_cria_arquivo_com_view_no_nome(
    client, auth_headers, sample_product, tmp_path
):
    response = client.post(
        f"/api/v1/products/{sample_product.id}/images/upload",
        files={"file": ("peca.png", _make_png(), "image/png")},
        params={"view": "frente"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert "original_frente" in data["original_url"], (
        f"URL deveria conter 'original_frente', recebeu: {data['original_url']}"
    )


def test_upload_costas_cria_arquivo_diferente_de_frente(
    client, auth_headers, sample_product
):
    # Upload frente
    client.post(
        f"/api/v1/products/{sample_product.id}/images/upload",
        files={"file": ("frente.png", _make_png(), "image/png")},
        params={"view": "frente"},
        headers=auth_headers,
    )
    # Upload costas
    response = client.post(
        f"/api/v1/products/{sample_product.id}/images/upload",
        files={"file": ("costas.png", _make_png(), "image/png")},
        params={"view": "costas"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert "original_costas" in data["original_url"]
    assert "original_frente" not in data["original_url"]


def test_upload_quatro_views_geram_arquivos_distintos(
    client, auth_headers, sample_product
):
    views = ["frente", "costas", "lat_direita", "lat_esquerda"]
    urls = []

    for view in views:
        response = client.post(
            f"/api/v1/products/{sample_product.id}/images/upload",
            files={"file": (f"{view}.png", _make_png(), "image/png")},
            params={"view": view},
            headers=auth_headers,
        )
        assert response.status_code == 201
        urls.append(response.json()["data"]["original_url"])

    # Todas as URLs devem ser distintas
    assert len(set(urls)) == 4, f"URLs duplicadas detectadas: {urls}"

    # Cada URL deve conter o nome da view
    for view, url in zip(views, urls):
        assert view in url, f"View '{view}' não encontrada na URL: {url}"


def test_upload_sem_view_usa_nome_original_sem_sufixo(
    client, auth_headers, sample_product
):
    response = client.post(
        f"/api/v1/products/{sample_product.id}/images/upload",
        files={"file": ("peca.png", _make_png(), "image/png")},
        headers=auth_headers,
    )
    assert response.status_code == 201
    url = response.json()["data"]["original_url"]
    # Sem view: deve ser original.png (sem sufixo de view)
    assert url.endswith("original.png"), f"URL sem view deveria terminar em original.png: {url}"


def test_public_url_reflete_nome_com_view(
    client, auth_headers, sample_product
):
    response = client.post(
        f"/api/v1/products/{sample_product.id}/images/upload",
        files={"file": ("peca.png", _make_png(), "image/png")},
        params={"view": "lat_direita"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["public_url"].startswith("/static/uploads/")
    assert "lat_direita" in data["public_url"]
