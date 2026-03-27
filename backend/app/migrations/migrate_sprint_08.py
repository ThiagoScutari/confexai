"""
Migration Sprint 08 — Adiciona campos de rastreabilidade em generation_jobs
e cria tabela job_api_logs.
Idempotente.
"""
import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://confexai:confexai@localhost/confexai_db")
engine = create_engine(DATABASE_URL)


def add_column_if_not_exists(conn, table, column, definition):
    result = conn.execute(text(
        f"SELECT column_name FROM information_schema.columns "
        f"WHERE table_name='{table}' AND column_name='{column}'"
    ))
    if not result.fetchone():
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))
        print(f"✅ Coluna '{column}' adicionada em {table}.")
    else:
        print(f"✅ Coluna '{column}' já existe em {table}.")


def migrate():
    with engine.begin() as conn:
        # Campos novos em generation_jobs
        add_column_if_not_exists(conn, "generation_jobs", "prompt_used", "TEXT NULL")
        add_column_if_not_exists(conn, "generation_jobs", "model_used", "VARCHAR(100) NULL")
        add_column_if_not_exists(conn, "generation_jobs", "duration_ms", "INTEGER NULL")
        add_column_if_not_exists(conn, "generation_jobs", "input_image_url", "VARCHAR(500) NULL")
        add_column_if_not_exists(conn, "generation_jobs", "fallback_reason", "TEXT NULL")

        # Tabela de logs de API (request/response brutos)
        result = conn.execute(text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
            "WHERE table_schema='public' AND table_name='job_api_logs')"
        ))
        if not result.scalar():
            conn.execute(text("""
                CREATE TABLE job_api_logs (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    job_id UUID NOT NULL REFERENCES generation_jobs(id) ON DELETE CASCADE,
                    request_payload TEXT,
                    response_payload TEXT,
                    http_status INTEGER,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """))
            print("✅ Tabela 'job_api_logs' criada.")
        else:
            print("✅ Tabela 'job_api_logs' já existe.")


if __name__ == "__main__":
    migrate()
