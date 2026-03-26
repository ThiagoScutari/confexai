"""
Migration Sprint 02 — Adiciona campo view em product_images.
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
            WHERE table_name='product_images' AND column_name='view'
        """))
        if not result.fetchone():
            conn.execute(text(
                "ALTER TABLE product_images ADD COLUMN view VARCHAR(30) NULL"
            ))
            print("✅ Campo 'view' adicionado em product_images.")
        else:
            print("✅ Campo 'view' ja existe.")


if __name__ == "__main__":
    migrate()
