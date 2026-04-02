# Base de Conhecimento — Pipeline de Variacao de Cor

**Data:** 2026-04-02
**Origem:** PDCA apos bug de colisao de arquivos identificado em producao
**Status:** Resolvido — validado com teste de ferro 4 views x 3 cores = 12 jobs

---

## O Bug

Jobs diferentes do mesmo produto + cor + view geravam o mesmo path de arquivo:
`color_{HEX}_{VIEW}.png`

Cada nova execucao sobrescrevia o arquivo anterior. O banco apontava para o
mesmo path, mas o conteudo no disco era da ultima execucao. Resultado: um job
de `frente` podia mostrar a imagem de `lat_direita` se essa fosse a execucao
mais recente.

**Evidencia:** `color_978B7B_frente.jpg` tinha 10 jobs apontando para o mesmo
arquivo. Apenas 1 gerou o conteudo que estava no disco.

---

## A Causa Raiz

`output_path` em `backend/app/api/jobs.py` era construido apenas com
`color_hex + view`, sem identificador unico por job.

```python
# ANTES — colisao garantida entre execucoes
output_path = Path(image_path).parent / f"color_{safe_hex}{view_suffix}.png"

# DEPOIS — cada job tem seu proprio arquivo
job_short_id = str(job.id)[:8]
output_path = Path(image_path).parent / f"color_{safe_hex}{view_suffix}_{job_short_id}.png"
```

**Pre-requisito:** `db.flush()` antes de construir o path para que `job.id`
ja exista.

---

## A Solucao

Incluir `job.id[:8]` no nome do arquivo. Novo padrao:

```
color_{HEX}_{VIEW}_{JOB_SHORT_ID}.{ext}
Exemplo: color_696980_frente_ae894d68.jpg
```

Isso torna fisicamente impossivel qualquer colisao entre jobs.

---

## Regras que NUNCA devem ser violadas

1. **`output_path` SEMPRE inclui `job.id[:8]`** — sem excecao
2. **`db.flush()` ANTES de construir `output_path`** — para garantir que `job.id` existe
3. **`color_hex` SEMPRE salvo no `result` JSON** — frontend depende disso para exibir a cor correta
4. **`cost_cents = 0` para Pillow, `cost_cents = 3` para Gemini** — custo nao pode ser hardcoded
5. **Gemini e SEMPRE primario** — Pillow e fallback com `fallback_reason` registrado

---

## Ordem correta no loop de cores

```python
for color_hex in payload.target_colors:
    # 1. Construir variaveis
    safe_hex = color_hex.replace("#", "").upper()
    view_suffix = f"_{image.view}" if image.view else ""

    # 2. Criar job e fazer flush para obter job.id
    job = GenerationJob(
        type=JobType.color_variation,
        status=JobStatus.pending,
        product_image_id=image.id,
    )
    db.add(job)
    db.flush()  # <- OBRIGATORIO antes do output_path

    # 3. Construir output_path com job.id (sem colisao)
    job_short_id = str(job.id)[:8]
    output_path = Path(image_path).parent / f"color_{safe_hex}{view_suffix}_{job_short_id}.png"

    # 4. Chamar Gemini (primario) com fallback Pillow
    result = apply_color_variation(image_bytes, color_hex, protected_regions, output_path)

    # 5. Salvar resultado com color_hex explicito
    job.result = json.dumps({**result, "color_hex": color_hex})
    job.status = JobStatus.pending_review
    db.commit()
```

---

## Teste de Ferro (validacao obrigatoria apos qualquer mudanca no pipeline)

```bash
# Criar produto, fazer upload de 4 views, gerar 3 cores cada
# Validar:
# - 12 jobs gerados
# - 24 arquivos no disco (12 PNG + 12 JPG)
# - 12 filenames unicos (zero colisao)
# - Todos via Gemini
# - color_hex correto nos 12 results
# - 4 views x 3 cores = distribuicao correta
```

**Aprovacao necessaria:** somente o arquiteto pode declarar o teste de ferro
aprovado apos validacao visual das imagens.

---

## Symptoms do bug (para diagnostico futuro)

- Job de `frente` mostra imagem de outra view
- `color_hex` no frontend nao bate com a cor solicitada
- Mesmo arquivo referenciado por multiplos jobs no banco
- Imagem com aparencia de "negativo" = Pillow foi usado em vez de Gemini
- `method: pillow_fallback` nos logs = verificar `GOOGLE_API_KEY` e SDK
