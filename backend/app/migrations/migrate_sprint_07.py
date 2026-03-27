"""
Migration Sprint 07 — Adiciona campo is_archived em generation_jobs.
Idempotente.
"""
import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://confexai:confexai@localhost/confexai_db")
engine = create_engine(DATABASE_URL)


def migrate():
    with engine.begin() as conn:
        result = conn.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name='generation_jobs' AND column_name='is_archived'
        """))
        if not result.fetchone():
            conn.execute(text(
                "ALTER TABLE generation_jobs ADD COLUMN is_archived BOOLEAN NOT NULL DEFAULT FALSE"
            ))
            print("✅ Campo 'is_archived' adicionado em generation_jobs.")
        else:
            print("✅ Campo 'is_archived' ja existe.")


if __name__ == "__main__":
    migrate()
