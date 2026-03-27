"""Rollback Sprint 13."""
import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://confexai:confexai@localhost/confexai_db")
engine = create_engine(DATABASE_URL)


def rollback():
    with engine.begin() as conn:
        conn.execute(text("DROP INDEX IF EXISTS ix_seo_descriptions_product_platform"))
        print("✅ Índice ix_seo_descriptions_product_platform removido.")

        result = conn.execute(text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
            "WHERE table_name='seo_descriptions' AND column_name='updated_at')"
        ))
        if result.scalar():
            conn.execute(text("ALTER TABLE seo_descriptions DROP COLUMN updated_at"))
            print("✅ Coluna 'updated_at' removida de seo_descriptions.")


if __name__ == "__main__":
    rollback()
