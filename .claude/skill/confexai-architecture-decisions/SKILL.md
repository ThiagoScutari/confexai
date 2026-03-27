---
name: confexai-architecture-decisions
description: >
  Decisões arquiteturais e ADRs do ConfexAI (DRX Têxtil). Use esta SKILL
  sempre que for sugerir mudanças estruturais, novos padrões, bibliotecas,
  frameworks, ou abordagens de design no ConfexAI. Também use ao responder
  perguntas sobre "por que fazemos X dessa forma", ao avaliar trade-offs técnicos,
  ou ao planejar features que afetam a arquitetura. Esta SKILL previne sugestões
  que contradizem decisões já tomadas. Consulte sempre antes de propor mudanças
  estruturais ou de integração de APIs externas.
---

# ConfexAI — Decisões Arquiteturais (ADRs)

## Stack Tecnológico — Imutável por Decisão

| Camada | Tecnologia | Alternativas REJEITADAS |
|--------|-----------|------------------------|
| Backend | FastAPI + Python 3.12 | Django, Flask |
| ORM | SQLAlchemy 2.0 | Tortoise, Peewee |
| Banco | PostgreSQL 16 | MySQL, SQLite |
| Frontend | React + Vite + TailwindCSS | HTML/JS Vanilla, Vue, Angular |
| Auth (MVP) | PyJWT + bcrypt | Auth0, Cognito |
| Auth (SaaS) | Auth0 ou Supabase Auth | Solução própria multi-tenant |
| Remoção de fundo | rembg (local) + Gemini fallback | Remove.bg API paga |
| Variação de cor | Gemini Imagen 3 (inpaint com máscara) | Stable Diffusion local, Replicate |
| Vídeo UGC | KlingAI | Runway, Pika, Sora |
| SEO/Análise | Claude claude-sonnet-4-20250514 (Anthropic) | GPT-4o, Gemini Flash |
| Fila assíncrona | NÃO no MVP — PostgreSQL jobs table | Celery, Redis, RabbitMQ |

---

## ADR-01 — React no Frontend (não HTML/JS Vanilla)

**Decisão:** React + Vite + TailwindCSS.

**Contexto:** ConfexAI tem estado complexo que o SGP Costura não tem:
fila de imagens, progresso por etapa de processamento, múltiplas variações
simultâneas, preview de máscara de estampa, player de vídeo.

**Por quê não Vanilla JS:**
- Gerenciar estado de uma fila de 5 variações de cor com etapas
  (upload → remoção de fundo → detecção de estampa → geração → revisão)
  em Vanilla JS resultaria em código frágil e difícil de manter
- React permite componentização real (JobCard, ColorPicker, MaskEditor)
- Visão SaaS exige routing, auth, dashboards — React escala bem nisso

**Rejeitar:** Sugestões de voltar para Vanilla JS, Alpine.js, ou HTMX.

---

## ADR-02 — Sem Fila Assíncrona no MVP

**Decisão:** Jobs síncronos no MVP. Tabela `generation_jobs` no PostgreSQL
como preparação para fila futura.

**Contexto:** Volume do MVP é ~10 SKUs × 5 cores = 50 gerações/ciclo.
Cada geração leva 5–15 segundos. Não justifica Celery + Redis.

**Como funciona no MVP:**
- Endpoint POST `/api/jobs` cria o job no banco (status: `pending`)
- Worker thread do FastAPI executa a geração e atualiza status
- Frontend faz polling a cada 3s no endpoint GET `/api/jobs/{id}`

**Migração para fila real (Fase 3):**
- Substituir worker thread por Celery worker
- Adicionar Redis como broker
- Nenhuma mudança no modelo de dados nem na API pública

**Rejeitar:** Sugestões de adicionar Celery no MVP.

---

## ADR-03 — rembg Local como Primeira Camada de Remoção de Fundo

**Decisão:** `rembg` (Python, gratuito, local) como motor primário.
Gemini Vision como fallback para casos complexos.

**Por quê:**
- Custo zero para o volume do MVP
- rembg funciona muito bem para peças sobre fundo branco/neutro
- Latência menor (sem chamada de rede)

**Quando usar Gemini fallback:**
- Score de confiança do rembg < 0.85
- Fundo não é branco/neutro
- Peça tem transparências (renda, tule)

**Rejeitar:** Remove.bg (pago por imagem), sugestão de usar sempre Gemini.

---

## ADR-04 — Detecção de Regiões Protegidas via Claude Vision

**Decisão:** Claude claude-sonnet-4-20250514 com visão analisa a peça e retorna
coordenadas/máscara de regiões protegidas (estampas, bordados, patches).

**Contexto:** Regra de negócio crítica — estampas e bordados nunca mudam
de cor junto com a peça base. O sistema deve preservar essas regiões.

**Fluxo:**
1. Claude Vision recebe o PNG da peça + prompt de detecção
2. Retorna JSON com bounding boxes das regiões protegidas
3. Sistema gera máscara binária a partir das bounding boxes
4. Operador revisa e ajusta a máscara via interface visual
5. Gemini Imagen aplica inpaint SOMENTE na área não mascarada

**Formato de retorno do Claude:**
```json
{
  "protected_regions": [
    {
      "type": "estampa",
      "description": "estampa floral no centro do corpo",
      "bbox": {"x": 120, "y": 80, "width": 200, "height": 180},
      "confidence": 0.94
    }
  ],
  "has_protected_regions": true
}
```

**Rejeitar:** Detectar regiões via prompt dentro do Gemini Imagen
(não confiável), ou pular detecção e deixar só para o operador.

---

## ADR-05 — Aprovação Humana Obrigatória no MVP

**Decisão:** Nenhum asset sai do sistema sem revisão humana no MVP.

**Fluxo de aprovação:**
```
Geração → status: pending_review → Operador revisa → approved/rejected
```

**Jobs rejeitados:**
- Podem ser regenerados com parâmetros ajustados (ex: intensidade de cor menor)
- Motivo de rejeição registrado no banco para análise de qualidade

**Automação futura (Fase 3):**
- Score de qualidade automático baseado em histórico de aprovações
- Auto-aprovar quando score > threshold configurável

**Rejeitar:** Sugestão de tornar aprovação opcional no MVP.

---

## ADR-06 — Tracking de Custo por Job

**Decisão:** Todo job de geração registra custo estimado em centavos.

**Por quê:** Viabilidade SaaS depende de entender custo real por operação.
Com 10 SKUs × 5 cores no MVP, já dá para calibrar preço do serviço.

**Tabela `generation_jobs`:**
```python
cost_cents: int      # custo estimado em centavos BRL
api_used: str        # "anthropic" | "gemini" | "klingai" | "rembg"
tokens_used: int     # para APIs baseadas em tokens
```

**Rejeitar:** Deixar custo como "TBD" para fase SaaS.

---

## ADR-07 — Migrações Manuais (mesmo padrão do SGP)

**Decisão:** Scripts Python idempotentes em `backend/app/migrations/`.
Sem Alembic. Sem auto-migrate no startup.

**Padrão:**
```
backend/app/migrations/
  migrate_sprint_NN.py   ← aplica mudança
  revert_sprint_NN.py    ← rollback
```

**Rejeitar:** Alembic, auto-migrate, Django-style migrations.

---

## ADR-08 — Soft Delete Universal

**Decisão:** Nunca hard delete em entidades de negócio.

```python
# ✅ CORRETO
is_active: bool = Column(Boolean, default=True)

# ❌ PROIBIDO em entidade de negócio
db.delete(entity)
```

**Entidades protegidas:** `products`, `product_images`, `seo_descriptions`,
`generation_jobs`.

---

## ADR-09 — Output Padrão de Imagens

**Decisão:** Toda imagem gerada é exportada em dois formatos:
- `JPG 1200×1200px` — para upload nas plataformas (ML, Shopee, Shopify)
- `PNG com fundo transparente` — para uso editorial e composições futuras

**Sem marca d'água** (decisão de negócio confirmada).

**Rejeitar:** Sugestões de outros formatos ou resoluções como padrão.

---

## O que NÃO Fazer — Anti-Patterns

| Anti-pattern | Por quê é proibido | Alternativa |
|-------------|-------------------|-------------|
| Celery + Redis no MVP | Overkill para volume atual | PostgreSQL jobs table + polling |
| Remove.bg API | Pago por imagem, custo desnecessário | rembg local + Gemini fallback |
| Gemini para SEO/análise | Claude tem melhor visão de produto têxtil | Claude claude-sonnet-4-20250514 |
| Publicação automática no MVP | Sem aprovação humana, risco de erro | Export manual, aprovação obrigatória |
| Hard delete de jobs | Perde histórico de custo e qualidade | `is_active = False` |
| Alembic | Risco em produção | Scripts manuais idempotentes |
| Vanilla JS no frontend | Estado complexo ingerenciável | React + Vite |
