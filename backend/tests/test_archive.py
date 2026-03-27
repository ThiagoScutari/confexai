import pytest


def test_archive_job_retorna_200(client, auth_headers, sample_job_pending_review):
    response = client.patch(
        f"/api/v1/jobs/{sample_job_pending_review.id}/archive",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["data"]["is_archived"] is True


def test_unarchive_job_retorna_200(client, auth_headers, sample_job_pending_review):
    # Arquivar primeiro
    client.patch(
        f"/api/v1/jobs/{sample_job_pending_review.id}/archive",
        headers=auth_headers,
    )
    # Depois desarquivar
    response = client.patch(
        f"/api/v1/jobs/{sample_job_pending_review.id}/unarchive",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["data"]["is_archived"] is False


def test_archive_sem_token_retorna_403(client, sample_job_pending_review):
    response = client.patch(f"/api/v1/jobs/{sample_job_pending_review.id}/archive")
    assert response.status_code == 403


def test_archive_job_inexistente_retorna_404(client, auth_headers):
    response = client.patch(
        "/api/v1/jobs/00000000-0000-0000-0000-000000000000/archive",
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_jobs_arquivados_nao_aparecem_na_lista(client, auth_headers, sample_job_pending_review):
    # Arquivar job
    client.patch(
        f"/api/v1/jobs/{sample_job_pending_review.id}/archive",
        headers=auth_headers,
    )
    # Verificar que não aparece na listagem padrão
    response = client.get("/api/v1/jobs", headers=auth_headers)
    ids = [j["id"] for j in response.json()["data"]]
    assert str(sample_job_pending_review.id) not in ids


def test_jobs_arquivados_aparecem_com_include_archived(client, auth_headers, sample_job_pending_review):
    client.patch(
        f"/api/v1/jobs/{sample_job_pending_review.id}/archive",
        headers=auth_headers,
    )
    response = client.get(
        "/api/v1/jobs?include_archived=true",
        headers=auth_headers,
    )
    ids = [j["id"] for j in response.json()["data"]]
    assert str(sample_job_pending_review.id) in ids
