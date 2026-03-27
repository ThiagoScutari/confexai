"""Rollback Sprint 07 — Remove campo is_archived de generation_jobs."""
import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://confexai:confexai@localhost/confexai_db")
engine = create_engine(DATABASE_URL)


def rollback():
    with engine.begin() as conn:
        result = conn.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name='generation_jobs' AND column_name='is_archived'
        """))
        if result.fetchone():
            conn.execute(text("ALTER TABLE generation_jobs DROP COLUMN is_archived"))
            print("✅ Coluna 'is_archived' removida de generation_jobs.")
        else:
            print("✅ Coluna 'is_archived' não existe — nada a fazer.")


if __name__ == "__main__":
    rollback()
