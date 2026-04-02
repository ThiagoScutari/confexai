"""Tests for cleanup_broken_jobs endpoint — Sprint 17.1."""


def test_cleanup_nao_afeta_jobs_soft_deleted(client, auth_headers, sample_product, db):
    """Jobs com deleted_at não devem ser processados pelo cleanup."""
    from datetime import datetime
    from app.models import GenerationJob, JobType, JobStatus, ProductImage

    image = ProductImage(
        product_id=sample_product.id,
        type="color_variant",
        original_url="/tmp/test_cleanup.png",
    )
    db.add(image)
    db.flush()

    job = GenerationJob(
        product_image_id=image.id,
        type=JobType.color_variation,
        status=JobStatus.done,
        result='{"jpg_url": "/static/uploads/naoexiste/color_x_00000000.jpg"}',
        deleted_at=datetime.utcnow(),
    )
    db.add(job)
    db.commit()

    response = client.delete("/api/v1/jobs/cleanup-broken", headers=auth_headers)
    assert response.status_code == 200

    still_exists = db.query(GenerationJob).filter(
        GenerationJob.id == job.id
    ).first()
    assert still_exists is not None, "cleanup removeu job com deleted_at — violação ADR-003"

    db.delete(job)
    db.delete(image)
    db.commit()


def test_cleanup_sem_token_retorna_403(client):
    response = client.delete("/api/v1/jobs/cleanup-broken")
    assert response.status_code == 403
