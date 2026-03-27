# PRD — Sprint 13: Backlog Técnico do Sprint 12

**Status:** Aprovação Pendente
**Origem:** Itens 🟡 identificados pela auditoria do Sprint 12
**Data:** 2026-03-26
**Objetivo:** Resolver os 3 itens de backlog técnico pendentes — `updated_at` na tabela SEO, índice composto e rate limiting no endpoint de geração.

---

## Sumário Executivo

| ID | Tipo | Descrição | Severidade |
|---|---|---|---|
| S13-01 | feat | Migration: `updated_at` em `seo_descriptions` | 🟡 |
| S13-02 | perf | Migration: índice composto `(product_id, platform)` em `seo_descriptions` | 🟡 |
| S13-03 | security | Rate limiting no endpoint `POST /products/{id}/seo` | 🟡 |
| S13-04 | test | Testes para os 3 itens acima | 🟡 |

---

## S13-01 — Migration: `updated_at` em `seo_descriptions`

### Motivação
A tabela `seo_descriptions` permite UPDATE (substituição de descrição existente) mas não tem `updated_at`. Impossível saber quando uma descrição foi regenerada.

### `backend/app/migrations/migrate_sprint_13.py`

```python
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
```

### `backend/app/migrations/rollback_sprint_13.py`

```python
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
```

### Atualizar `backend/app/models.py` — adicionar campo

```python
class SEODescription(Base):
    __tablename__ = "seo_descriptions"
    # ... campos existentes ...
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)
```

### Atualizar GET /products/{id}/seo — incluir `updated_at` na resposta

```python
# Em backend/app/api/products.py, na função get_seo_descriptions:
return StandardResponse(data=[
    {
        "id": str(d.id),
        "platform": d.platform,
        "title": d.title,
        "title_char_count": len(d.title),
        "description": d.description,
        "tags": json.loads(d.tags) if d.tags else [],
        "is_approved": d.is_approved,
        "created_at": d.created_at.isoformat(),
        "updated_at": d.updated_at.isoformat() if d.updated_at else d.created_at.isoformat(),  # ← novo
    }
    for d in descriptions
])
```

### Atualizar POST /products/{id}/seo — setar `updated_at` no UPDATE

```python
# No bloco de substituição (existing):
if existing:
    existing.title = title
    existing.description = description
    existing.tags = json.dumps(tags, ensure_ascii=False)
    existing.is_approved = False
    existing.updated_at = datetime.utcnow()  # ← novo
```

---

## S13-02 — Índice Composto (já coberto na migration S13-01)

O índice `ix_seo_descriptions_product_platform` é criado na mesma migration. Sem código adicional necessário.

**Impacto:** a query `filter(product_id=X, platform=Y)` que ocorre a cada geração SEO passa de full scan para index scan.

---

## S13-03 — Rate Limiting no Endpoint de Geração SEO

### Motivação
Cada chamada a `POST /products/{id}/seo` dispara 1 + N chamadas ao Claude (1 análise + N plataformas = até 4 chamadas). Sem rate limit, um clique duplo ou script pode gerar custo descontrolado.

### Solução: rate limiting simples via dict em memória (sem Redis)

**Decisão:** no MVP, sem Redis, usamos um dict em memória com timestamp por usuário. Simples, eficaz para uso single-user.

```python
# Adicionar em backend/app/api/products.py (após imports)

from datetime import datetime, timedelta
from fastapi import Request

# Rate limit: 1 geração SEO por produto a cada 30 segundos por usuário
_seo_rate_limit: dict[str, datetime] = {}
SEO_RATE_LIMIT_SECONDS = 30


def _check_seo_rate_limit(user_key: str, product_id: str) -> None:
    """
    Levanta HTTPException 429 se o usuário gerou SEO para este produto
    nos últimos SEO_RATE_LIMIT_SECONDS segundos.
    """
    key = f"{user_key}:{product_id}"
    now = datetime.utcnow()
    last = _seo_rate_limit.get(key)
    if last and (now - last).total_seconds() < SEO_RATE_LIMIT_SECONDS:
        remaining = SEO_RATE_LIMIT_SECONDS - int((now - last).total_seconds())
        raise HTTPException(
            429,
            detail=f"Aguarde {remaining}s antes de gerar SEO novamente para este produto."
        )
    _seo_rate_limit[key] = now
```

### Aplicar no endpoint

```python
@router.post("/{product_id}/seo", status_code=202)
def generate_seo(
    product_id: UUID,
    payload: SEOGenerateRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),  # ← mudar de _user para current_user
):
    # Rate limit check
    _check_seo_rate_limit(
        user_key=current_user.get("user_id", "default"),
        product_id=str(product_id)
    )
    # ... restante do código ...
```

---

## S13-04 — Testes

### `backend/tests/test_seo_ratelimit.py`

```python
import pytest
from unittest.mock import patch, MagicMock
import time


def _mock_seo():
    mock = MagicMock()
    mock.analyze_garment.return_value = ({"garment_type": "blusa"}, 100)
    mock.generate_for_platform.return_value = (
        {
            "title": "Blusa Teste",
            "description": "Descrição teste",
            "keywords": ["blusa"],
            "title_char_count": 11,
            "seo_score_rationale": "ok",
        },
        100,
        [],
    )
    return mock


def test_segunda_geracao_imediata_retorna_429(
    client, auth_headers, sample_product, sample_image_uploaded
):
    """Duas gerações seguidas para o mesmo produto devem bloquear a segunda."""
    with patch("app.api.products.SEOGeneratorService") as MockSvc:
        MockSvc.return_value = _mock_seo()
        # Primeira geração — deve passar
        r1 = client.post(
            f"/api/v1/products/{sample_product.id}/seo",
            json={"platforms": ["mercadolivre"]},
            headers=auth_headers,
        )
        assert r1.status_code == 202

        # Segunda geração imediata — deve ser bloqueada
        r2 = client.post(
            f"/api/v1/products/{sample_product.id}/seo",
            json={"platforms": ["mercadolivre"]},
            headers=auth_headers,
        )
        assert r2.status_code == 429
        assert "Aguarde" in r2.json()["detail"]


def test_produtos_diferentes_nao_interferem(
    client, auth_headers, sample_product, sample_image_uploaded, db
):
    """Rate limit é por produto — produtos diferentes não interferem."""
    from app.models import Product, ProductImage
    from pathlib import Path
    import os
    import io
    from PIL import Image as PILImage

    # Criar segundo produto com imagem
    p2 = Product(name="TEST_PROD_Segundo", category="calça", fabric="algodão")
    db.add(p2)
    db.commit()

    upload_dir = Path(os.getenv("UPLOAD_DIR", "/app/examples/uploads"))
    p2_dir = upload_dir / str(p2.id)
    p2_dir.mkdir(parents=True, exist_ok=True)
    img_path = p2_dir / "original_frente.png"
    img = PILImage.new("RGBA", (600, 600), (100, 100, 100, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    img_path.write_bytes(buf.getvalue())

    img2 = ProductImage(
        product_id=p2.id, type="original", view="frente",
        original_url=str(img_path)
    )
    db.add(img2)
    db.commit()

    with patch("app.api.products.SEOGeneratorService") as MockSvc:
        MockSvc.return_value = _mock_seo()
        # Gerar para produto 1
        r1 = client.post(
            f"/api/v1/products/{sample_product.id}/seo",
            json={"platforms": ["mercadolivre"]},
            headers=auth_headers,
        )
        assert r1.status_code == 202

        # Gerar para produto 2 — deve passar (produto diferente)
        r2 = client.post(
            f"/api/v1/products/{p2.id}/seo",
            json={"platforms": ["mercadolivre"]},
            headers=auth_headers,
        )
        assert r2.status_code == 202

    # Cleanup
    db.delete(img2)
    db.delete(p2)
    db.commit()
    if img_path.exists():
        img_path.unlink()


def test_updated_at_presente_na_resposta(
    client, auth_headers, sample_product, sample_image_uploaded
):
    """GET /seo deve retornar updated_at em cada descrição."""
    with patch("app.api.products.SEOGeneratorService") as MockSvc:
        MockSvc.return_value = _mock_seo()
        client.post(
            f"/api/v1/products/{sample_product.id}/seo",
            json={"platforms": ["mercadolivre"]},
            headers=auth_headers,
        )

    response = client.get(
        f"/api/v1/products/{sample_product.id}/seo",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) > 0
    assert "updated_at" in data[0], "Campo updated_at ausente na resposta"
```

---

## Ordem de Execução

```
S13-01 (models.py + migration + rollback)
  ↓
S13-03 (rate limiting em products.py)
  ↓
S13-04 (testes)
  ↓
Rodar migration + testes
  ↓
Auditoria (ANTES DO COMMIT)
  ↓
Commits
```

---

## Commits Atômicos

```
feat(db): add updated_at to seo_descriptions and composite index sprint 13 migration [S13-01-02]
feat(db): add rollback script for sprint 13 [S13-01]
fix(api): add rate limiting to POST /products/{id}/seo endpoint [S13-03]
test(sprint13): add 3 tests for rate limiting and updated_at field [S13-04]
```

---

## Critérios de Aceite

- [ ] Migration S13 roda sem erros — `updated_at` criado, índice criado
- [ ] Rollback S13 é idempotente
- [ ] `GET /products/{id}/seo` retorna `updated_at` em cada descrição
- [ ] Segunda geração imediata retorna HTTP 429 com mensagem de espera
- [ ] Produtos diferentes não interferem no rate limit
- [ ] `pytest tests/ -v` → **68 passed, 0 failed**
- [ ] Auditoria aprovada ANTES dos commits
