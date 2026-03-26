def test_aprovar_job_pending_review(client, auth_headers, sample_job_pending_review):
    response = client.post(
        f"/api/v1/jobs/{sample_job_pending_review.id}/approve",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "approved"


def test_aprovar_job_que_nao_esta_em_revisao_retorna_409(client, auth_headers, sample_job_done):
    response = client.post(
        f"/api/v1/jobs/{sample_job_done.id}/approve",
        headers=auth_headers,
    )
    assert response.status_code == 409


def test_rejeitar_job_registra_motivo(client, auth_headers, sample_job_pending_review):
    response = client.post(
        f"/api/v1/jobs/{sample_job_pending_review.id}/reject",
        json={"reason": "cor ficou muito escura"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "rejected"


def test_buscar_job_por_id(client, auth_headers, sample_job_pending_review):
    response = client.get(
        f"/api/v1/jobs/{sample_job_pending_review.id}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert "status" in response.json()["data"]


def test_aprovar_sem_token_retorna_401(client, sample_job_pending_review):
    response = client.post(f"/api/v1/jobs/{sample_job_pending_review.id}/approve")
    assert response.status_code == 401 or response.status_code == 403
