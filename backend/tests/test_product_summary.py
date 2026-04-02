"""Tests for GET /products/{id}/summary endpoint — Sprint 17.3."""


def test_summary_sem_token_retorna_403(client, sample_product):
    response = client.get(f"/api/v1/products/{sample_product.id}/summary")
    assert response.status_code == 403


def test_summary_produto_inexistente_retorna_404(client, auth_headers):
    response = client.get(
        "/api/v1/products/00000000-0000-0000-0000-000000000000/summary",
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_summary_retorna_estrutura_completa(client, auth_headers, sample_product):
    response = client.get(
        f"/api/v1/products/{sample_product.id}/summary",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    for key in ["product", "images", "approved_variations", "seo", "stats"]:
        assert key in data
    assert "total_jobs" in data["stats"]
    assert "total_cost_brl" in data["stats"]
    assert "views_uploaded" in data["stats"]
    assert "variations_approved" in data["stats"]
    assert "platforms_with_seo" in data["stats"]


def test_summary_produto_inativo_retorna_404(client, auth_headers, db):
    from app.models import Product
    p = Product(name="TEST_DEL", category="blusa", fabric="viscose", is_active=False)
    db.add(p)
    db.commit()
    response = client.get(f"/api/v1/products/{p.id}/summary", headers=auth_headers)
    assert response.status_code == 404
    db.delete(p)
    db.commit()


def test_summary_nao_inclui_jobs_deletados(client, auth_headers, sample_product, db):
    """Stats não devem contar jobs com deleted_at."""
    from datetime import datetime
    from app.models import GenerationJob, ProductImage, JobType, JobStatus

    img = db.query(ProductImage).filter(
        ProductImage.product_id == sample_product.id
    ).first()
    if not img:
        img = ProductImage(
            product_id=sample_product.id,
            type="original",
            view="frente",
            original_url="/tmp/test_summary.png",
        )
        db.add(img)
        db.flush()

    job = GenerationJob(
        product_image_id=img.id,
        type=JobType.color_variation,
        status=JobStatus.approved,
        deleted_at=datetime.utcnow(),
        cost_cents=3,
    )
    db.add(job)
    db.commit()

    response = client.get(
        f"/api/v1/products/{sample_product.id}/summary",
        headers=auth_headers,
    )
    data = response.json()["data"]
    job_ids = [v["id"] for v in data["approved_variations"]]
    assert str(job.id) not in job_ids

    db.delete(job)
    db.commit()
