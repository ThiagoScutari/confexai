"""
Migration Sprint 09 — Índices de performance + limpeza de dívida técnica.
Idempotente.
"""
import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://confexai:confexai@localhost/confexai_db")
engine = create_engine(DATABASE_URL)


def index_exists(conn, index_name: str) -> bool:
    result = conn.execute(text(
        f"SELECT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = '{index_name}')"
    ))
    return result.scalar()


def migrate():
    with engine.begin() as conn:
        # Índice em job_api_logs.job_id — queries por job degradam sem isso
        if not index_exists(conn, "ix_job_api_logs_job_id"):
            conn.execute(text(
                "CREATE INDEX ix_job_api_logs_job_id ON job_api_logs(job_id)"
            ))
            print("✅ Índice ix_job_api_logs_job_id criado.")
        else:
            print("✅ Índice ix_job_api_logs_job_id já existe.")

        # Índice em generation_jobs.created_at — GET /history usa ORDER BY created_at DESC
        if not index_exists(conn, "ix_generation_jobs_created_at"):
            conn.execute(text(
                "CREATE INDEX ix_generation_jobs_created_at ON generation_jobs(created_at DESC)"
            ))
            print("✅ Índice ix_generation_jobs_created_at criado.")
        else:
            print("✅ Índice ix_generation_jobs_created_at já existe.")

        # Índice em generation_jobs.is_archived — filtro mais usado
        if not index_exists(conn, "ix_generation_jobs_is_archived"):
            conn.execute(text(
                "CREATE INDEX ix_generation_jobs_is_archived ON generation_jobs(is_archived)"
            ))
            print("✅ Índice ix_generation_jobs_is_archived criado.")
        else:
            print("✅ Índice ix_generation_jobs_is_archived já existe.")

        # Índice em product_images.product_id — JOINs frequentes
        if not index_exists(conn, "ix_product_images_product_id"):
            conn.execute(text(
                "CREATE INDEX ix_product_images_product_id ON product_images(product_id)"
            ))
            print("✅ Índice ix_product_images_product_id criado.")
        else:
            print("✅ Índice ix_product_images_product_id já existe.")


if __name__ == "__main__":
    migrate()
