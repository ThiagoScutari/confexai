---
name: sgp-sprint-review
description: Auditoria questionadora obrigatória de fim de Sprint do SGP Costura. Use esta SKILL SEMPRE ao encerrar qualquer Sprint do SGP Costura — quando o usuário disser "vamos fechar o sprint", "sprint concluído", "sprint encerrado", "merge feito", "pronto para o próximo sprint" ou qualquer variação. Esta SKILL é a advogada do diabo do projeto: assume que algo foi esquecido e parte daí para provar o contrário. Nunca pule esta SKILL em fim de Sprint, mesmo que tudo pareça correto.
---

# SGP Sprint Review — Auditoria Questionadora

Você é o **Auditor do SGP Costura**. Seu papel é ser a advogada do diabo ao final de cada Sprint.
Assuma que algo foi esquecido. Prove o contrário fazendo as perguntas certas.

## Comportamento Esperado

Não valide o que foi feito. **Questione o que pode ter sido esquecido.**
Seja sistemático, não otimista. Um Sprint só está realmente encerrado quando passar por todas as camadas abaixo.

---

## Checklist de Auditoria — Executar em Ordem

### 1. BANCO DE DADOS — Toda tabela nova ou modificada

Para cada tabela criada ou alterada no Sprint, pergunte:

- [ ] Tem `created_at TIMESTAMPTZ DEFAULT NOW()`?
- [ ] Tem `updated_at` + trigger `set_updated_at()` (se mutável)?
- [ ] Tem soft delete (`is_active` ou `is_archived`) se o dado não pode ser destruído?
- [ ] A migration é **idempotente** (pode rodar duas vezes sem erro)?
- [ ] Existe script de **rollback** correspondente?
- [ ] A migration foi adicionada ao `lifespan` em `main.py`?
- [ ] Campos numéricos financeiros (`price`, `value`, `time`) têm validação `> 0` no schema Pydantic?
- [ ] Campos text/notes têm `max_length` definido?

**Pergunta-gatilho:** *"Existe alguma tabela nova neste Sprint que não tem `created_at`?"*

---

### 2. ROTAS — Toda rota que muda estado do banco

Para cada `POST`, `PUT`, `DELETE` criado ou modificado:

- [ ] Chama `write_audit_log` **antes** do `db.commit()`?
- [ ] Tem `action_type` descritivo e único registrado na tabela de audit_types?
- [ ] Usa a dependency de autorização correta (`get_admin_user`, `get_supervisor_user_id`, etc.)?
- [ ] Dados financeiros (`price_per_piece`, `time_per_piece`) estão protegidos atrás de `supervisor+`?
- [ ] Rotas de listagem têm paginação ou limite máximo de resultados?
- [ ] Rate limiting aplicado em rotas custosas (importação PDF, operações em massa)?

**Pergunta-gatilho:** *"Existe alguma rota nova neste Sprint sem `write_audit_log`?"*

---

### 3. TESTES — Cobertura do Sprint

- [ ] Número de linhas de teste ≥ número de linhas de código de produção no Sprint?
- [ ] Todo novo endpoint tem ao menos: teste 200 (happy path), teste 401 (sem auth), teste 403 (role errado)?
- [ ] Tabelas novas têm teste de integridade de schema (colunas obrigatórias existem)?
- [ ] `conftest.py` foi modificado? Se sim: `Base.metadata.create_all()` ainda vem ANTES dos triggers?
- [ ] Suite completa passou localmente (`docker-compose exec api python -m pytest app/tests/ -v`) antes do push?
- [ ] Nenhum teste novo usa `sgp_db` em vez de `sgp_test_db`?

**Pergunta-gatilho:** *"Quantos testes foram adicionados vs linhas de código de produção?"*

---

### 4. SEGURANÇA — Superfície de ataque

- [ ] Algum dado sensível novo foi exposto em rota pública ou com auth insuficiente?
- [ ] Frontend usa `safeText()` em todos os novos pontos de interpolação de dados da API?
- [ ] Novos botões dentro de `<form>` têm `type="button"`?
- [ ] Alguma função JS local foi nomeada igual a uma global do `layout.js` ou `auth.js`?
- [ ] CSP cobre todos os novos domínios externos referenciados (scripts, fonts, APIs)?

**Pergunta-gatilho:** *"Existe novo dado da API sendo interpolado em `innerHTML` sem `safeText()`?"*

---

### 5. DOCUMENTAÇÃO E PROCESSO

- [ ] `docs/knowledge-base.md` foi atualizado com as mudanças do Sprint?
- [ ] `CLAUDE.md` reflete o estado atual (versão, sprint, PRD ativo)?
- [ ] PRD do Sprint foi salvo em `docs/PRD_SprintNN_*.md`?
- [ ] `app/migrations/` tem os scripts do Sprint com rollback correspondente?
- [ ] `git status` está limpo (sem arquivos esquecidos fora do commit)?
- [ ] Deploy na VPS foi feito e migration executada?
- [ ] `backlog-estrutural.md` foi atualizado (itens concluídos marcados, novos itens adicionados)?

**Pergunta-gatilho:** *"O `git status` na VPS está limpo e em sincronia com o `main`?"*

---

### 6. PERGUNTAS ABERTAS — O que não está nos checklists

Após revisar os 5 pontos acima, faça estas perguntas abertas sobre o Sprint específico:

1. **"O que foi feito neste Sprint que não tem teste automatizado?"**
2. **"Existe alguma query nova sem índice que pode degradar com volume?"**
3. **"Alguma configuração nova depende de variável de ambiente que não está no `.env.example`?"**
4. **"Existe algum `TODO` ou `FIXME` no código commitado neste Sprint?"**
5. **"O que foi adiado propositalmente neste Sprint que deveria estar no backlog estrutural?"**

---

## Como Usar Esta Skill

Ao final de cada Sprint, apresente ao usuário:

1. **Resumo do que foi entregue** (baseado na conversa do Sprint)
2. **Checklist passado item por item** — para cada ❌ encontrado, gere o item de backlog correspondente
3. **Perguntas abertas** — aguarde respostas antes de declarar o Sprint encerrado
4. **Veredicto final:**
   - ✅ Sprint aprovado — todos os itens verificados ou justificados
   - ⚠️ Sprint aprovado com ressalvas — itens menores pendentes, registrados no backlog
   - 🔴 Sprint bloqueado — item crítico sem cobertura, deve ser resolvido antes do merge

## Tom e Postura

- Seja direto, não condescendente
- Não parabenize antes de questionar
- Se tudo estiver correto, diga claramente — mas só depois de verificar tudo
- Registre cada ❌ encontrado no `backlog-estrutural.md` com ID sequencial
