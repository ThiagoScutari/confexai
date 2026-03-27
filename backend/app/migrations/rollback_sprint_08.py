"""Rollback Sprint 08 — Remove campos de rastreabilidade e tabela job_api_logs."""
import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://confexai:confexai@localhost/confexai_db")
engine = create_engine(DATABASE_URL)

COLUMNS_TO_DROP = [
    "prompt_used", "model_used", "duration_ms",
    "input_image_url", "fallback_reason"
]


def rollback():
    with engine.begin() as conn:
        # Remover tabela job_api_logs
        conn.execute(text("DROP TABLE IF EXISTS job_api_logs CASCADE"))
        print("✅ Tabela 'job_api_logs' removida.")

        # Remover colunas de generation_jobs
        for col in COLUMNS_TO_DROP:
            result = conn.execute(text(f"""
                SELECT column_name FROM information_schema.columns
                WHERE table_name='generation_jobs' AND column_name='{col}'
            """))
            if result.fetchone():
                conn.execute(text(f"ALTER TABLE generation_jobs DROP COLUMN {col}"))
                print(f"✅ Coluna '{col}' removida de generation_jobs.")
            else:
                print(f"✅ Coluna '{col}' não existe — nada a fazer.")


if __name__ == "__main__":
    rollback()
