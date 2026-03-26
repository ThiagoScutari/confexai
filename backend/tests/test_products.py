import pytest

PAYLOAD_VALIDO = {
    "name": "TEST_PROD_Blusa Sprint01",
    "category": "blusa",
    "fabric": "viscose",
    "notes": "produto criado em teste automatizado"
}


def test_criar_produto_sem_token_retorna_401(client):
    response = client.post("/api/v1/products", json=PAYLOAD_VALIDO)
    assert response.status_code == 401 or response.status_code == 403


def test_criar_produto_valido_retorna_201(client, auth_headers):
    response = client.post("/api/v1/products", json=PAYLOAD_VALIDO, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["name"] == PAYLOAD_VALIDO["name"]
    assert "id" in data
    assert data["is_active"] is True


def test_criar_produto_nome_curto_retorna_422(client, auth_headers):
    payload = {**PAYLOAD_VALIDO, "name": "AB"}
    response = client.post("/api/v1/products", json=payload, headers=auth_headers)
    assert response.status_code == 422


def test_criar_produto_sem_category_retorna_422(client, auth_headers):
    payload = {k: v for k, v in PAYLOAD_VALIDO.items() if k != "category"}
    response = client.post("/api/v1/products", json=payload, headers=auth_headers)
    assert response.status_code == 422


def test_listar_produtos_retorna_lista(client, auth_headers, sample_product):
    response = client.get("/api/v1/products", headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json()["data"], list)


def test_buscar_produto_por_id(client, auth_headers, sample_product):
    response = client.get(f"/api/v1/products/{sample_product.id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["data"]["id"] == str(sample_product.id)


def test_buscar_produto_inexistente_retorna_404(client, auth_headers):
    response = client.get(
        "/api/v1/products/00000000-0000-0000-0000-000000000000",
        headers=auth_headers
    )
    assert response.status_code == 404


def test_deletar_produto_soft_delete(client, auth_headers, sample_product):
    response = client.delete(
        f"/api/v1/products/{sample_product.id}",
        headers=auth_headers
    )
    assert response.status_code == 200
    # Produto nao aparece mais na listagem
    list_response = client.get("/api/v1/products", headers=auth_headers)
    ids = [p["id"] for p in list_response.json()["data"]]
    assert str(sample_product.id) not in ids
