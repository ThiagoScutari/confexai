"""Tests for soft delete (deleted_at) endpoint — Sprint 15."""


def test_delete_job_sem_token_retorna_403(client, sample_job_pending_review):
    response = client.patch(f"/api/v1/jobs/{sample_job_pending_review.id}/delete")
    assert response.status_code == 403


def test_delete_job_retorna_200_com_deleted_at(client, auth_headers, sample_job_pending_review):
    response = client.patch(
        f"/api/v1/jobs/{sample_job_pending_review.id}/delete",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert "deleted_at" in response.json()["data"]


def test_job_deletado_nao_aparece_na_listagem(client, auth_headers, sample_job_pending_review):
    client.patch(
        f"/api/v1/jobs/{sample_job_pending_review.id}/delete",
        headers=auth_headers,
    )
    response = client.get("/api/v1/jobs", headers=auth_headers)
    ids = [j["id"] for j in response.json()["data"]]
    assert str(sample_job_pending_review.id) not in ids


def test_job_deletado_nao_aparece_no_historico(client, auth_headers, sample_job_pending_review):
    client.patch(
        f"/api/v1/jobs/{sample_job_pending_review.id}/delete",
        headers=auth_headers,
    )
    response = client.get("/api/v1/jobs/history", headers=auth_headers)
    ids = [j["id"] for j in response.json()["data"]]
    assert str(sample_job_pending_review.id) not in ids


def test_delete_job_inexistente_retorna_404(client, auth_headers):
    response = client.patch(
        "/api/v1/jobs/00000000-0000-0000-0000-000000000000/delete",
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_delete_job_duas_vezes_retorna_404(client, auth_headers, sample_job_pending_review):
    client.patch(
        f"/api/v1/jobs/{sample_job_pending_review.id}/delete",
        headers=auth_headers,
    )
    response = client.patch(
        f"/api/v1/jobs/{sample_job_pending_review.id}/delete",
        headers=auth_headers,
    )
    assert response.status_code == 404
