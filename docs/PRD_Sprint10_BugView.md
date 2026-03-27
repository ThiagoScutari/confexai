# PRD — Sprint 10: Correção do Bug de View no Upload de Imagens

**Status:** Aprovação Pendente
**Origem:** Bug crítico — todas as views processam a mesma imagem física
**Data:** 2026-03-26
**Severidade:** 🔴 Crítico — invalida o pipeline completo de variação de cor

---

## Causa Raiz

`backend/app/api/images.py` linha 75:

```python
# PROBLEMA — nome fixo sobrescreve o arquivo anterior
file_path = product_dir / f"original{Path(file.filename).suffix}"
```

Cada upload para o mesmo produto usa o nome `original.png`, sobrescrevendo o arquivo anterior no disco. O banco registra `view` corretamente, mas `original_url` aponta para o mesmo arquivo físico em todos os registros.

**Resultado:** ao rodar variação de cor nas 4 views, o Gemini recebe sempre a última imagem enviada.

---

## Sumário Executivo

| ID | Tipo | Descrição | Esforço |
|---|---|---|---|
| S10-01 | fix | Incluir `view` no nome do arquivo salvo no disco | Pequeno |
| S10-02 | fix | Limpar imagens órfãs do banco (registros com URL duplicada) | Pequeno |
| S10-03 | fix | `public_url` do upload refletir o novo path com view | Pequeno |
| S10-04 | test | Testes cobrindo o novo comportamento de nomenclatura | Médio |

---

## S10-01 — Fix: Incluir `view` no Nome do Arquivo

### `backend/app/api/images.py` — linha 75

```python
# ANTES (linha 75):
file_path = product_dir / f"original{Path(file.filename).suffix}"

# DEPOIS:
view_suffix = f"_{view}" if view else ""
file_path = product_dir / f"original{view_suffix}{Path(file.filename).suffix}"
```

**Exemplos de arquivo gerado:**
- `frente` → `original_frente.png`
- `costas` → `original_costas.png`
- `lat_direita` → `original_lat_direita.png`
- `lat_esquerda` → `original_lat_esquerda.png`
- sem view → `original.png` (comportamento legado preservado)

### Código completo do bloco de salvar arquivo (substituir linhas 73-76):

```python
# Salvar arquivo com nome único por view
product_dir = UPLOAD_DIR / str(product_id)
product_dir.mkdir(parents=True, exist_ok=True)
view_suffix = f"_{view}" if view else ""
file_path = product_dir / f"original{view_suffix}{Path(file.filename).suffix}"
file_path.write_bytes(content)
```

---

## S10-02 — Limpeza de Imagens Órfãs

Imagens existentes no banco apontam para `original.png` (sobrescrito). Precisam ser marcadas como arquivadas para não poluir novos pipelines.

### Endpoint de limpeza (já existe `cleanup-broken`) — usar direto:

```bash
# Arquivar jobs de variação de cor que apontam para imagens possivelmente corrompidas
# (imagens antigas com original.png que pode ser a view errada)
# Executar após o fix para que novos uploads usem o nome correto
```

**Ação manual recomendada:** recriar os produtos de teste com novas imagens após o fix. Os jobs antigos já estão arquivados da limpeza anterior.

---

## S10-03 — `public_url` reflete o novo path

O campo `public_url` é calculado por `path_to_url(image.original_url)` — como `original_url` agora terá o nome correto, `public_url` será atualizado automaticamente. Sem mudança necessária.

**Verificar:** `path_to_url` em `url_helper.py` não hardcoda nenhum nome de arquivo.

```python
# url_helper.py — confirmar que é genérico
def path_to_url(file_path: str | Path) -> str:
    path = Path(file_path)
    relative = path.relative_to(UPLOAD_DIR)
    return f"/static/uploads/{relative}"
```

✅ Genérico — funciona com qualquer nome de arquivo.

---

## S10-04 — Testes

### `backend/tests/test_upload_view_naming.py`

```python
import io
from PIL import Image as PILImage
from pathlib import Path


def _make_png(width=600, height=600) -> bytes:
    img = PILImage.new("RGBA", (width, height), (150, 100, 80, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_upload_frente_cria_arquivo_com_view_no_nome(
    client, auth_headers, sample_product, tmp_path
):
    response = client.post(
        f"/api/v1/products/{sample_product.id}/images/upload",
        files={"file": ("peca.png", _make_png(), "image/png")},
        params={"view": "frente"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert "original_frente" in data["original_url"], (
        f"URL deveria conter 'original_frente', recebeu: {data['original_url']}"
    )


def test_upload_costas_cria_arquivo_diferente_de_frente(
    client, auth_headers, sample_product
):
    # Upload frente
    client.post(
        f"/api/v1/products/{sample_product.id}/images/upload",
        files={"file": ("frente.png", _make_png(), "image/png")},
        params={"view": "frente"},
        headers=auth_headers,
    )
    # Upload costas
    response = client.post(
        f"/api/v1/products/{sample_product.id}/images/upload",
        files={"file": ("costas.png", _make_png(), "image/png")},
        params={"view": "costas"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert "original_costas" in data["original_url"]
    assert "original_frente" not in data["original_url"]


def test_upload_quatro_views_geram_arquivos_distintos(
    client, auth_headers, sample_product
):
    views = ["frente", "costas", "lat_direita", "lat_esquerda"]
    urls = []

    for view in views:
        response = client.post(
            f"/api/v1/products/{sample_product.id}/images/upload",
            files={"file": (f"{view}.png", _make_png(), "image/png")},
            params={"view": view},
            headers=auth_headers,
        )
        assert response.status_code == 201
        urls.append(response.json()["data"]["original_url"])

    # Todas as URLs devem ser distintas
    assert len(set(urls)) == 4, f"URLs duplicadas detectadas: {urls}"

    # Cada URL deve conter o nome da view
    for view, url in zip(views, urls):
        assert view in url, f"View '{view}' não encontrada na URL: {url}"


def test_upload_sem_view_usa_nome_original_sem_sufixo(
    client, auth_headers, sample_product
):
    response = client.post(
        f"/api/v1/products/{sample_product.id}/images/upload",
        files={"file": ("peca.png", _make_png(), "image/png")},
        headers=auth_headers,
    )
    assert response.status_code == 201
    url = response.json()["data"]["original_url"]
    # Sem view: deve ser original.png (sem sufixo de view)
    assert url.endswith("original.png"), f"URL sem view deveria terminar em original.png: {url}"


def test_public_url_reflete_nome_com_view(
    client, auth_headers, sample_product
):
    response = client.post(
        f"/api/v1/products/{sample_product.id}/images/upload",
        files={"file": ("peca.png", _make_png(), "image/png")},
        params={"view": "lat_direita"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["public_url"].startswith("/static/uploads/")
    assert "lat_direita" in data["public_url"]
```

---

## Ordem de Execução

```
S10-01 (fix linha 75 em images.py)
  ↓
S10-04 (testes)
  ↓
Rodar testes (target: 55 passed, 0 failed)
  ↓
Verificação manual: subir 4 imagens e conferir arquivos distintos em disco
  ↓
S10-02 (limpeza de dados antigos — manual)
  ↓
Commits
```

---

## Commits Atômicos

```
fix(images): include view in uploaded filename to prevent file overwrite [S10-01]
test(sprint10): add 5 tests for view-based filename uniqueness [S10-04]
```

---

## Critérios de Aceite

- [ ] Upload de `frente` salva `original_frente.png` em disco
- [ ] Upload de `costas` salva `original_costas.png` em disco (não sobrescreve frente)
- [ ] Upload de 4 views do mesmo produto resulta em 4 arquivos distintos no disco
- [ ] Upload sem `view` continua salvando `original.png` (compatibilidade legada)
- [ ] `public_url` retornado contém o nome da view
- [ ] Pipeline de variação de cor processa imagens distintas para cada view
- [ ] `pytest tests/ -v` → **55 passed, 0 failed**
- [ ] Verificação manual: subir frente + costas, rodar pipeline, confirmar no Histórico que as imagens de entrada são diferentes
