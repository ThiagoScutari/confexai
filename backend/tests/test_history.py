from uuid import uuid4


def test_history_sem_token_retorna_401_ou_403(client):
    response = client.get("/api/v1/jobs/history")
    assert response.status_code in (401, 403)


def test_history_com_token_retorna_200(client, auth_headers):
    response = client.get("/api/v1/jobs/history", headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json()["data"], list)


def test_history_limite_padrao_50(client, auth_headers):
    response = client.get("/api/v1/jobs/history", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()["data"]) <= 50


def test_history_com_limit_customizado(client, auth_headers):
    response = client.get("/api/v1/jobs/history?limit=5", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()["data"]) <= 5


def test_history_campos_obrigatorios_presentes(client, auth_headers):
    response = client.get("/api/v1/jobs/history", headers=auth_headers)
    data = response.json()["data"]
    if len(data) > 0:
        job = data[0]
        required = ["id", "type", "status", "cost_cents", "created_at",
                    "is_archived", "cost_brl"]
        for field in required:
            assert field in job, f"Campo '{field}' ausente no retorno do history"


def test_history_filtro_por_product_id_invalido(client, auth_headers):
    fake_id = str(uuid4())
    response = client.get(
        f"/api/v1/jobs/history?product_id={fake_id}",
        headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["data"] == []
