"""Rollback Sprint 09 — Remove índices criados."""
import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://confexai:confexai@localhost/confexai_db")
engine = create_engine(DATABASE_URL)


def rollback():
    with engine.begin() as conn:
        for idx in [
            "ix_job_api_logs_job_id",
            "ix_generation_jobs_created_at",
            "ix_generation_jobs_is_archived",
            "ix_product_images_product_id",
        ]:
            conn.execute(text(f"DROP INDEX IF EXISTS {idx}"))
            print(f"✅ Índice {idx} removido.")


if __name__ == "__main__":
    rollback()
