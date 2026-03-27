"""
Migration Sprint 13 — updated_at em seo_descriptions + índice composto.
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


def column_exists(conn, table: str, column: str) -> bool:
    result = conn.execute(text(
        f"SELECT EXISTS (SELECT 1 FROM information_schema.columns "
        f"WHERE table_name='{table}' AND column_name='{column}')"
    ))
    return result.scalar()


def migrate():
    with engine.begin() as conn:

        # 1. updated_at em seo_descriptions
        if not column_exists(conn, "seo_descriptions", "updated_at"):
            conn.execute(text(
                "ALTER TABLE seo_descriptions "
                "ADD COLUMN updated_at TIMESTAMP DEFAULT NOW()"
            ))
            # Preencher updated_at com created_at para registros existentes
            conn.execute(text(
                "UPDATE seo_descriptions SET updated_at = created_at "
                "WHERE updated_at IS NULL"
            ))
            print("✅ Coluna 'updated_at' adicionada em seo_descriptions.")
        else:
            print("✅ Coluna 'updated_at' já existe em seo_descriptions.")

        # 2. Índice composto (product_id, platform) em seo_descriptions
        if not index_exists(conn, "ix_seo_descriptions_product_platform"):
            conn.execute(text(
                "CREATE INDEX ix_seo_descriptions_product_platform "
                "ON seo_descriptions(product_id, platform)"
            ))
            print("✅ Índice ix_seo_descriptions_product_platform criado.")
        else:
            print("✅ Índice ix_seo_descriptions_product_platform já existe.")


if __name__ == "__main__":
    migrate()
