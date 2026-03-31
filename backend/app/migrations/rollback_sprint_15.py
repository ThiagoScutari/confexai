"""Rollback Sprint 15 — remove deleted_at de generation_jobs."""
import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://confexai:confexai@localhost/confexai_db")
engine = create_engine(DATABASE_URL)


def rollback():
    with engine.begin() as conn:
        conn.execute(text(
            "DROP INDEX IF EXISTS ix_generation_jobs_deleted_at"
        ))
        print("✅ Índice 'ix_generation_jobs_deleted_at' removido.")

        conn.execute(text(
            "ALTER TABLE generation_jobs DROP COLUMN IF EXISTS deleted_at"
        ))
        print("✅ Coluna 'deleted_at' removida.")


if __name__ == "__main__":
    rollback()
