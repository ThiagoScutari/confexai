"""
Migration Sprint 01 — Criacao das tabelas base do ConfexAI.
Idempotente: seguro rodar multiplas vezes.
"""
import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://confexai:confexai@localhost/confexai_db")
engine = create_engine(DATABASE_URL)


def table_exists(conn, table_name: str) -> bool:
    result = conn.execute(text(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
        "WHERE table_schema='public' AND table_name=:t)"
    ), {"t": table_name})
    return result.scalar()


def migrate():
    from app.database import Base
    from app import models  # garante que todos os modelos sao importados

    with engine.begin() as conn:
        # Criar banco de teste se nao existir
        conn.execute(text("COMMIT"))
        try:
            conn.execute(text("CREATE DATABASE confexai_test_db"))
            print("✅ Banco de teste confexai_test_db criado.")
        except Exception:
            print("✅ Banco de teste ja existe.")

    Base.metadata.create_all(bind=engine)
    print("✅ Tabelas criadas: products, product_images, generation_jobs, seo_descriptions")


if __name__ == "__main__":
    migrate()
