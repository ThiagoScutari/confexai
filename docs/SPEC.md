# ConfexAI — Especificação do Sistema (SPEC.md)

**Versão:** 1.0 — Sprint 14  
**Última atualização:** 2026-03-26  
**Status:** Documento vivo — atualizar a cada sprint que altere fluxos ou critérios

---

## 1. Propósito

Automatizar o fluxo de fotografia de produto para confecções têxteis. Dada uma foto de peça (PNG com fundo transparente), o sistema gera:

- Variações de cor via Gemini Imagen
- Fundos alternativos lifestyle (futuro)
- Descrições SEO por plataforma (ML, Shopee, Shopify)
- Vídeos UGC (futuro — KlingAI)

**Operador primário:** usuário técnico único (MVP). Visão futura: SaaS multi-tenant.

---

## 2. Stack Técnico — Imutável

| Camada | Tecnologia | Versão |
|---|---|---|
| Backend | FastAPI + Python | 3.12 |
| ORM | SQLAlchemy | 2.0 |
| Banco | PostgreSQL | 16 |
| Frontend | React + Vite + TailwindCSS | React 18, Vite 5, Tailwind 3 |
| Roteamento | React Router DOM | 6 |
| HTTP client | Axios | 1.7 |
| IA — Análise/SEO | Anthropic Claude | claude-sonnet-4-20250514 |
| IA — Imagem | Google Gemini | google-genai 1.7, gemini-2.0-flash-exp |
| IA — Vídeo | KlingAI | reservado, não implementado |
| Containers | Docker Compose V2 | sem hífen |
| Portas | api: 8002, db: 5435, frontend: 5173 | — |

---

## 3. Fluxos de Usuário

### 3.1 Fluxo Principal — Variação de Cor

```
[Login]
   ↓
[Produtos] → Criar produto (nome, categoria, tecido)
   ↓
[Pipeline] → Upload das views (frente, costas, lat_direita, lat_esquerda)
           → Selecionar cores alvo (HEX)
           → Modal de confirmação com custo estimado
           → Executar pipeline
               ↓ Remoção de fundo (rembg — skip se já transparente)
               ↓ Detecção de regiões protegidas (Claude Vision)
               ↓ Variação de cor por view × cor (Gemini)
   ↓
[Resultados] → Revisar cards por produto
             → Aprovar / Rejeitar individualmente
             → Arquivar (soft delete visual)
             → Download por imagem / produto / multi-produto (ZIP)
   ↓
[Histórico] → Ver todas as execuções com prompt, métricas, custo
```

### 3.2 Fluxo SEO

```
[Produtos] → Clicar em "SEO"
   ↓
[SEO] → Selecionar plataformas (ML, Shopee, Shopify)
      → Informar cores disponíveis (opcional)
      → Gerar SEO (Claude Vision analisa frente da peça)
          ↓ Análise da peça (garment_type, fabric, style...)
          ↓ Geração por plataforma (título + descrição + tags)
          ↓ Validação de limites de caracteres
      → Ver resultado por plataforma com botões de cópia
      → Regenerar se necessário (rate limit: 30s por produto)
```

### 3.3 Fluxo de Recuperação de Resultados

```
Usuário navega para fora durante pipeline
   ↓
[Produtos] → Botão "Resultados" em cada produto
   ↓
[Resultados] → Jobs agrupados por produto
             → Aprovar/Rejeitar pendentes
             → Botão "Atualizar" para recarregar
```

---

## 4. Critérios de Aceite por Módulo

### 4.1 Upload de Imagens
- ✅ Formatos aceitos: PNG, JPG
- ✅ Tamanho máximo: 20MB
- ✅ Resolução mínima: 500×500px
- ✅ Cada view gera arquivo distinto em disco (`original_{view}.{ext}`)
- ✅ Upload sem view: salva como `original.{ext}` (compatibilidade legada)
- ✅ Preview da imagem aparece imediatamente após upload (FileReader)

### 4.2 Pipeline de Variação de Cor
- ✅ Rembg detecta transparência e pula remoção se já transparente
- ✅ Claude Vision retorna `has_protected_regions` + coordenadas de estampas/bordados
- ✅ Gemini gera variação com `method: "gemini"` sempre que possível
- ✅ Fallback Pillow ativa automaticamente se Gemini falhar
- ✅ `fallback_reason` registrado no banco se Pillow ativou
- ✅ Jobs gerados ficam em `status: pending_review` até aprovação humana
- ✅ Custo em centavos registrado por job

### 4.3 Resultados e Download
- ✅ Imagens servidas em `/static/uploads/` sem autenticação
- ✅ Download individual: `confexai_{color}_{view}_{hash6}.jpg`
- ✅ Download por produto: ZIP com todos os aprovados
- ✅ Download multi-produto: ZIP organizado por pasta de produto
- ✅ Archive = soft delete visual (`is_archived=True`), nunca hard delete
- ✅ Arquivados acessíveis via toggle "Ver arquivados"

### 4.4 Descrições SEO
- ✅ Mercado Livre: título ≤ 60 chars, 5 keywords
- ✅ Shopee: título ≤ 120 chars, exatamente 15 tags
- ✅ Shopify: título ≤ 70 chars, meta description 150-160 chars
- ✅ Segunda geração substitui (não duplica) no banco
- ✅ Rate limit: 30s por produto por usuário
- ✅ `updated_at` registrado a cada regeneração

### 4.5 Histórico
- ✅ Retorna prompt exato enviado à IA
- ✅ Retorna imagem de entrada e imagem de saída
- ✅ Custo em centavos e R$ por job
- ✅ Tempo de execução em ms
- ✅ Método usado (`gemini` ou `pillow_fallback`)
- ✅ Request/response bruto em `job_api_logs` (não exposto no frontend)

---

## 5. Antipadrões — O Que Nunca Fazer

### 5.1 Backend

```python
# ❌ PROIBIDO — hard delete em entidade de negócio
db.delete(job)

# ✅ CORRETO — soft delete
job.is_archived = True
db.commit()
```

```python
# ❌ PROIBIDO — expor erro interno ao cliente
raise HTTPException(500, detail=str(e))

# ✅ CORRETO — mensagem genérica + log interno
logger.error(f"Erro: {e}", exc_info=True)
raise HTTPException(500, detail="Erro interno do servidor.")
```

```python
# ❌ PROIBIDO — chamar API externa em testes
response = client.messages.create(...)  # sem mock

# ✅ CORRETO — sempre mockar
with patch("app.services.seo_generator.anthropic.Anthropic") as mock:
    ...
```

```python
# ❌ PROIBIDO — N+1 query
for j in jobs:
    prod = db.query(Product).filter(Product.id == j.product_id).first()

# ✅ CORRETO — prefetch
products_map = _prefetch_product_names(db, jobs)
```

```python
# ❌ PROIBIDO — migration não idempotente
conn.execute(text("ALTER TABLE t ADD COLUMN c VARCHAR"))  # falha se já existir

# ✅ CORRETO — verificar antes
if not column_exists(conn, "t", "c"):
    conn.execute(text("ALTER TABLE t ADD COLUMN c VARCHAR"))
```

### 5.2 Frontend

```jsx
// ❌ PROIBIDO — XSS via dangerouslySetInnerHTML com conteúdo do banco
<div dangerouslySetInnerHTML={{ __html: content }} />

// ✅ CORRETO — renderização segura
<div className="whitespace-pre-wrap">{content}</div>
```

```jsx
// ❌ PROIBIDO — chamada de API sem tratamento de erro
const res = await api.get("/endpoint");
setData(res.data);

// ✅ CORRETO — try/catch + toast
try {
  const res = await api.get("/endpoint");
  setData(res.data.data);
} catch (err) {
  toast(err.response?.data?.detail || "Erro ao carregar", "error");
}
```

```jsx
// ❌ PROIBIDO — estado de pipeline apenas em memória React
// (navegar para fora perde os resultados)

// ✅ CORRETO — sempre persistir no banco e redirecionar para /resultados
setTimeout(() => navigate(`/resultados/${productId}`), 1500);
```

```javascript
// ❌ PROIBIDO — plataforma como string livre
platforms: ["instagram"]  // aceita qualquer coisa

// ✅ CORRETO — Literal type no Pydantic + validação 422
platforms: list[Literal["mercadolivre", "shopee", "shopify"]]
```

### 5.3 Arquitetura

```
# ❌ PROIBIDO — Celery/Redis no MVP
# ❌ PROIBIDO — Alembic / auto-migrate no startup
# ❌ PROIBIDO — Hard delete em qualquer entidade de negócio
# ❌ PROIBIDO — response_mime_type: "image/png" no SDK google-generativeai (legado)
# ❌ PROIBIDO — Nome fixo de arquivo (original.png) sem view no upload
# ❌ PROIBIDO — CORS sem PATCH no allow_methods (quebra archive/unarchive)
```

---

## 6. Convenções de Código

### 6.1 Nomenclatura de Arquivos

| Tipo | Padrão | Exemplo |
|---|---|---|
| Imagem original | `original_{view}.{ext}` | `original_frente.png` |
| Variação de cor | `color_{HEX}_{view}.{ext}` | `color_696980_frente.jpg` |
| Download | `confexai_{color}_{view}_{hash6}.jpg` | `confexai_696980_frente_7ea99b.jpg` |
| Migration | `migrate_sprint_NN.py` | `migrate_sprint_13.py` |
| Rollback | `rollback_sprint_NN.py` | `rollback_sprint_13.py` |
| Teste | `test_{módulo}.py` | `test_seo_ratelimit.py` |

### 6.2 URLs Públicas de Imagens

```
Formato interno (container): /app/examples/uploads/{product_id}/{filename}
URL pública (browser):        /static/uploads/{product_id}/{filename}
Conversão:                    path_to_url() em backend/app/services/url_helper.py
```

### 6.3 Custo de API

| Operação | API | Custo real (calibrado Sprint 03/12) |
|---|---|---|
| Análise de peça (SEO) | Claude Sonnet | ~6¢ por imagem |
| Geração SEO por plataforma | Claude Sonnet | ~3¢ por plataforma |
| Detecção de regiões protegidas | Claude Sonnet | ~6¢ por imagem |
| Variação de cor | Gemini Imagen | ~3¢ por imagem |
| Remoção de fundo | rembg local | R$0,00 |

### 6.4 Padrão de Endpoint FastAPI

```python
@router.post("/recurso", status_code=201)
def create_recurso(
    payload: RecursoCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        # 1. Validação de negócio
        # 2. Criar/processar
        # 3. db.commit()
        # 4. return StandardResponse(data=...)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro: {e}", exc_info=True)
        raise HTTPException(500, detail="Erro interno do servidor.")
```

---

## 7. Limites e Restrições Conhecidas

| Restrição | Valor | Motivo |
|---|---|---|
| Tamanho máximo de upload | 20MB | Limite razoável para PNG de produto |
| Resolução mínima de upload | 500×500px | Mínimo para qualidade de geração |
| Rate limit SEO | 30s por produto | Evitar custo descontrolado com Claude |
| Jobs no histórico | 200 por chamada | Performance — paginar quando necessário |
| Plataformas SEO válidas | `mercadolivre`, `shopee`, `shopify` | Validado via Pydantic Literal |
| Views válidas | `frente`, `costas`, `lat_direita`, `lat_esquerda` | Validado via Query param pattern |
| Título ML | 60 chars | Limite real do Mercado Livre |
| Título Shopee | 120 chars | Limite real da Shopee |
| Título Shopify | 70 chars | Limite SEO recomendado |
| Tags Shopee | exatamente 15 | Requisito da plataforma |
| Meta description Shopify | 150-160 chars | SEO Google otimizado |

---

## 8. O Que NÃO Está Implementado (Backlog)

| Módulo | Status |
|---|---|
| Fundo alternativo lifestyle (Gemini) | 🔴 Não iniciado |
| Geração de vídeo UGC (KlingAI) | 🔴 Não iniciado |
| Autenticação multi-tenant (SaaS) | 🔴 Não iniciado |
| Publicação automática nas plataformas | 🔴 Não iniciado |
| Edição inline de descrições SEO | 🟡 Planejado |
| Integração com SGP Costura | 🟡 Fase 3 |
| Fila assíncrona (Celery + Redis) | 🟡 Quando volume > MVP |
| Paginação no histórico | 🟡 Quando > 200 jobs |
| Aprovação automática por score | 🟡 Fase 3 |

---

## 9. Definition of Done (DoD) por Sprint

Todo sprint só é considerado encerrado quando:

- [ ] `pytest tests/ -v` → N passed, **0 failed**
- [ ] Auditoria `sgp-sprint-review` rodou e retornou ✅ ou ⚠️ (nunca 🔴)
- [ ] Nenhum teste chama API externa real sem mock
- [ ] `git status` limpo (nenhum arquivo untracked relevante)
- [ ] `CLAUDE.md` atualizado com o sprint na tabela
- [ ] PRD do sprint commitado em `docs/`
- [ ] Migration tem rollback correspondente
- [ ] Migrations são idempotentes (podem rodar N vezes)
- [ ] Nenhum `dangerouslySetInnerHTML` com conteúdo externo sem sanitização
- [ ] Build do frontend sem erros (`Vite ready`)
- [ ] Verificação visual confirmada pelo operador antes dos commits
