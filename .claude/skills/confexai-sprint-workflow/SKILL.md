---
name: confexai-sprint-workflow
description: >
  Workflow obrigatório de desenvolvimento do ConfexAI (DRX Têxtil). Use esta
  SKILL sempre que for iniciar qualquer tarefa de desenvolvimento no ConfexAI —
  correção de bug, nova feature, refatoração, integração de API externa, ou
  atualização de testes. Define o ritual completo: inspeção → feedback →
  aprovação → implementação → testes → commits atômicos. Nunca pule etapas.
  Nunca implemente sem inspeção prévia aprovada. Use também ao planejar sprints,
  escrever PRDs, ou estruturar prompts de implementação para Claude Code.
---

# ConfexAI — Workflow de Sprint

## Filosofia Central

**A IA é o estagiário sênior, o humano é o arquiteto.**

- Nunca tome decisões arquiteturais sem debate
- Nunca implemente sem inspeção prévia aprovada
- Nunca commite sem pytest verde
- Sempre commits atômicos por bug/feature
- Nunca chamar APIs externas (Anthropic, Gemini, KlingAI) em testes

---

## O Ritual — 7 Passos Obrigatórios

### Passo 1 — Inspeção Cirúrgica

**Antes de qualquer implementação**, gerar prompt de inspeção para o Claude Code.
A inspeção deve:
- Mostrar arquivo, linha e código literal exato
- NÃO sugerir correções ainda
- NÃO modificar nenhum arquivo

```
# Formato do prompt de inspeção — ConfexAI
Read docs/PROJECT.md and docs/PRD_Sprint_NN_*.md.
Also read the relevant SKILL.md files for this task.

Do NOT implement anything yet. Inspection only.

1. [Item a inspecionar]
   - Show exact file:line and literal code
   - Confirm [condição específica]

2. [Próximo item]
   ...
```

### Passo 2 — Feedback e Análise

O arquiteto recebe o resultado da inspeção e reporta aqui.
Claude analisa:
- ✅ Confirmado — gap real, proceder
- ❌ Falso positivo — descartar, documentar
- ⚠️ Parcial — ajustar escopo antes de implementar

**Nunca avançar sem este passo.**

### Passo 3 — Aprovação

O arquiteto aprova explicitamente cada item confirmado.
Claude aguarda aprovação antes de gerar prompts de implementação.

### Passo 4 — Implementação

Gerar prompt de implementação para o Claude Code com:
- Ordem explícita de execução
- Arquivos e linhas exatas a modificar
- Referência às skills relevantes (image-pipeline, api-contracts, etc.)
- NÃO rodar pytest ainda
- NÃO commitar ainda

```
# Formato do prompt de implementação — ConfexAI
Implement in this exact order. Do NOT run pytest until all changes complete.
Reference: confexai-api-contracts/SKILL.md for endpoint patterns.
Reference: confexai-image-pipeline/SKILL.md for image processing.

── ITEM 1 ──────────────────────────
File: backend/app/api/images.py

[mudança específica com código exato]

── ITEM 2 ──────────────────────────
File: backend/app/services/background_removal.py
...

── AFTER ALL CHANGES ────────────────
docker-compose up -d --build
docker-compose exec api python -m pytest backend/tests/ -v

Target: NNN passed, 0 failed.
Do NOT commit until approved.
```

### Passo 5 — Testes

O Claude Code reporta resultado do pytest.
Claude analisa:
- ✅ `NNN passed, 0 failed` → aprovado para commit
- ❌ Falhas → identificar causa, corrigir, repetir pytest

**Nunca commitar com testes falhando.**

### Passo 6 — Commits Atômicos

Um commit por bug/feature. Nunca agrupar mudanças não relacionadas.

```bash
# Formato de commit message — ConfexAI
tipo(módulo): descrição curta em português [ID]

# Tipos válidos
feat     — nova feature
fix      — correção de bug
test     — apenas testes
docs     — documentação
refactor — refatoração sem mudança de comportamento
perf     — melhoria de performance
devops   — infraestrutura, CI, Docker
security — mudança de segurança
prompt   — ajuste de prompt (SEO, detecção, etc.)

# Exemplos reais do projeto
feat(images): add background removal endpoint with rembg [S01-01]
feat(jobs): add color variation job with Gemini inpainting [S01-02]
fix(seo): handle Claude Vision JSON parse error gracefully [S02-01]
test(images): add upload validation and rembg mock tests [S01-03]
prompt(seo): improve ML title generation to respect 60 char limit [S02-02]
```

### Passo 7 — PR e Merge

Abrir PR com descrição estruturada:
- O que muda (por item)
- Resultado dos testes
- APIs externas mockadas nos testes? (confirmar)
- Verificação manual realizada
- Checklist de aceite

Merge apenas após aprovação do arquiteto.

---

## Estrutura de PRD

Todo sprint começa com um PRD salvo em `docs/PRD_SprintNN_*.md`.

```markdown
# PRD — Sprint NN: Título
**Status:** Aprovação Pendente
**Origem:** [feature request / bug report / refatoração]

## Sumário Executivo
| ID | Severidade | Descrição | Esforço |

## SNN-01 — Nome do Item
### Evidência / Motivação
[arquivo:linha com código ou descrição do gap]

### APIs Externas Envolvidas
[Anthropic / Gemini / KlingAI / nenhuma]

### Implementação
[código exato ou abordagem]

### Testes
[cenários a cobrir, mocks necessários]

## Ordem de Execução
## Commits Atômicos
## Critérios de Aceite
```

---

## Atenção Especial — Jobs Assíncronos

Jobs de geração têm fluxo próprio que deve ser respeitado:

```
POST /api/v1/jobs → status: pending
      ↓ (worker thread / futuro Celery)
status: processing
      ↓
status: done | failed
      ↓ (aprovação humana obrigatória no MVP)
POST /api/v1/jobs/{id}/approve
      ↓
Disponível para export
```

**Ao implementar um novo tipo de job:**
1. Registrar o tipo em `generation_jobs.type` enum
2. Implementar o service correspondente em `backend/app/services/`
3. Mockar a API externa nos testes
4. Cobrir os cenários: pending → done, pending → failed, approve, reject

---

## Migrações de Banco de Dados

**Regras inegociáveis:**
- Sempre idempotentes
- Sempre acompanhadas de script de rollback
- Em `backend/app/migrations/migrate_sprint_NN.py`
- Rodar manualmente após deploy

```python
# Template — migration idempotente ConfexAI
def migrate():
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name='tabela' AND column_name='coluna'
        """))
        if not result.fetchone():
            conn.execute(text("ALTER TABLE tabela ADD COLUMN ..."))
            conn.commit()
            print("✅ Migração aplicada.")
        else:
            print("✅ Já estava atualizado.")
```

---

## Deploy

```bash
# Após merge no main
git pull origin main
docker-compose up -d --build
docker-compose exec api python backend/app/migrations/migrate_sprint_NN.py

# Verificar
docker-compose logs api --tail=20
```

**Checklist pós-deploy:**
- [ ] API responde em /api/v1/health
- [ ] Upload de imagem funciona
- [ ] Job de remoção de fundo processa
- [ ] Migration aplicada (verificar output)
- [ ] Zero erros no console do browser

---

## Severidade de Bugs

| 🔴 Crítico | Sistema quebrado, auth bypass, dados perdidos, chamada real a API cara |
|---|---|
| 🟡 Médio | Job falha sem feedback, resultado de baixa qualidade, UX degradada |
| 🟢 Baixo | Cosmético, log desnecessário, melhoria de prompt |

Bugs 🔴 bloqueiam o deploy.
