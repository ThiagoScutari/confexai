"""Migration Sprint 15 — deleted_at em generation_jobs. Idempotente."""
import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://confexai:confexai@localhost/confexai_db")
engine = create_engine(DATABASE_URL)


def column_exists(conn, table, column):
    r = conn.execute(text(
        f"SELECT EXISTS (SELECT 1 FROM information_schema.columns "
        f"WHERE table_name='{table}' AND column_name='{column}')"
    ))
    return r.scalar()


def index_exists(conn, index_name):
    r = conn.execute(text(
        f"SELECT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname='{index_name}')"
    ))
    return r.scalar()


def migrate():
    with engine.begin() as conn:
        # 1. Add deleted_at column
        if not column_exists(conn, "generation_jobs", "deleted_at"):
            conn.execute(text(
                "ALTER TABLE generation_jobs ADD COLUMN deleted_at TIMESTAMP NULL"
            ))
            print("✅ Coluna 'deleted_at' adicionada em generation_jobs.")
        else:
            print("✅ 'deleted_at' já existe.")

        # 2. Partial index for fast filtering of non-deleted jobs
        if not index_exists(conn, "ix_generation_jobs_deleted_at"):
            conn.execute(text(
                "CREATE INDEX ix_generation_jobs_deleted_at "
                "ON generation_jobs(deleted_at) WHERE deleted_at IS NULL"
            ))
            print("✅ Índice parcial 'ix_generation_jobs_deleted_at' criado.")
        else:
            print("✅ Índice 'ix_generation_jobs_deleted_at' já existe.")


if __name__ == "__main__":
    migrate()
