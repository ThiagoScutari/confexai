# ConfexAI — Instruções do Projeto Claude

## O que é este projeto

Plataforma de automação visual para confecção têxtil (DRX Têxtil). Dado uma foto de peça de roupa, gera variações de cor, descrições SEO e futuramente vídeos UGC.

**Repositório:** `C:\workspace\ConfexAI` | `https://github.com/ThiagoScutari/confexai.git`  
**Stack:** FastAPI (Python 3.12) + PostgreSQL + React + Vite + TailwindCSS  
**Portas:** api: 8002, db: 5435, frontend: 5173  
**Testes atuais:** 68 passando, 0 falhando

---

## Como trabalhar neste projeto

### Leitura obrigatória ao iniciar qualquer tarefa

Antes de qualquer implementação, o Claude Code deve ler:

```
Read docs/SPEC.md
Read docs/ROUTE_REFERENCE.md
Read .claude/skills/confexai-sprint-workflow/SKILL.md
```

Para tarefas de frontend, adicionar:
```
Read docs/claude-design-tokens.json
Read .claude/skills/confexai-api-contracts/SKILL.md
```

Para tarefas de pipeline de imagem:
```
Read .claude/skills/confexai-image-pipeline/SKILL.md
```

Para tarefas de SEO:
```
Read .claude/skills/confexai-seo-prompts/SKILL.md
```

---

## Workflow obrigatório (nunca pular etapas)

```
1. Inspeção   → Claude Code inspeciona sem modificar nada
2. Análise    → Claude analisa gaps e confirma com o arquiteto
3. Aprovação  → Arquiteto aprova escopo explicitamente
4. Implementação → Claude Code implementa
5. Testes     → pytest tests/ -v → N passed, 0 failed
5.5 Auditoria → sgp-sprint-review ANTES do commit (obrigatório)
6. Commits    → atômicos, um por feature/fix
7. Push       → git push origin main
8. Docs       → CLAUDE.md atualizado
```

**A auditoria no passo 5.5 é inegociável.** Foi introduzida após um bug de XSS ser commitado sem revisão no Sprint 12.

---

## Frontend — Onde estamos com mais dificuldade

### Paleta e identidade visual (não negociável)

Tema: **"Industrial Refinado"** — escuro, âmbar, tipografia DM.

```
surface-950: #0a0a0b  ← background principal
surface-900: #111113  ← sidebar
surface-800: #1a1a1f  ← cards
surface-700: #242429  ← inputs
surface-600: #2e2e35  ← bordas

amber-500:   #f59e0b  ← botão primário (background)
amber-400:   #fbbf24  ← texto de destaque, ícones ativos

neutral-100: #f5f5f4  ← texto primário
neutral-400: #a8a29e  ← texto de suporte
neutral-500: #78716c  ← labels, metadata
```

**Fontes:** DM Serif Display (títulos), DM Sans (corpo), JetBrains Mono (códigos, HEX, IDs)

**Nunca usar:** Inter, Roboto, fontes system-ui, gradientes roxos, fundo branco.

### Padrão de componente React

```jsx
// Estrutura padrão de página
export default function NomePagina() {
  const { toast } = useToast();
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchData()
      .then(r => setData(r.data.data))
      .catch(() => toast("Erro ao carregar", "error"))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingSkeleton />;

  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="font-display text-2xl text-neutral-100">Título</h1>
        <p className="text-sm text-neutral-500 mt-1">Subtítulo</p>
      </div>
    </div>
  );
}
```

### Chamadas de API — padrão obrigatório

```jsx
// CORRETO — sempre try/catch + toast
try {
  const res = await api.post("/endpoint", payload);
  setData(res.data.data);
  toast("Operação realizada com sucesso", "success");
} catch (err) {
  toast(err.response?.data?.detail || "Erro inesperado", "error");
}

// PROIBIDO — sem tratamento de erro
const res = await api.get("/endpoint");
setData(res.data);
```

### Segurança no frontend

```jsx
// PROIBIDO — XSS
<div dangerouslySetInnerHTML={{ __html: content }} />

// CORRETO — sempre renderização segura
<div className="whitespace-pre-wrap">{content}</div>
```

### Quando o resultado parecer genérico

Adicionar ao prompt do Claude Code:

```
Use the design tokens from docs/claude-design-tokens.json.
Theme: "Industrial Refinado" — dark, amber accents, DM fonts.
Never use Inter, Roboto, or purple gradients.
All cards: bg-surface-800 border border-surface-600 rounded-xl
Primary buttons: bg-amber-500 hover:bg-amber-400 text-surface-950
Headings: font-display (DM Serif Display)
Mono text (HEX, IDs, timestamps): font-mono (JetBrains Mono)
```

---

## Backend — Padrões críticos

### Endpoint FastAPI padrão

```python
@router.post("/recurso", status_code=201)
def create_recurso(
    payload: RecursoCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        # lógica
        db.commit()
        return StandardResponse(data=result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro: {e}", exc_info=True)
        raise HTTPException(500, detail="Erro interno do servidor.")
```

### Antipadrões que já quebraram sprints

| Antipadrão | Consequência | Sprint |
|---|---|---|
| `response_mime_type: "image/png"` | HTTP 400 no Gemini | 03 |
| `original.png` sem view no nome | Sobrescreve outras views | 10 |
| CORS sem `PATCH` | Archive falha silenciosamente | 07 |
| `db.delete(entity)` | Dados perdidos | 01 |
| `dangerouslySetInnerHTML` sem sanitização | XSS | 12 |
| `platforms: list[str]` no Pydantic | Aceita valores inválidos | 12 |
| API externa sem mock em teste | Custo real em testes | 02 |
| Migration não idempotente | Falha em redeploy | 05 |

---

## Testes — regras

- Nunca chamar Anthropic, Gemini ou KlingAI em testes — sempre mockar
- Banco de teste: `confexai_test_db` (nunca `confexai_db`)
- Todo endpoint novo precisa de: teste 200 + teste 401/403 + teste 404
- Fixtures de imagem usam PIL para criar PNG real em disco

---

## Decisões imutáveis

Formalizadas em `docs/decisions/ADRs.md`. Não contestar ou reverter:

- React no frontend (não Vanilla JS, não Alpine, não Vue)
- `google-genai` SDK com `response_modalities=["IMAGE", "TEXT"]`
- Migrations manuais (não Alembic)
- Sem Celery no MVP
- rembg local como motor primário
- `Literal` types no Pydantic para campos com valores fixos
- Soft delete universal — nunca `db.delete()` em entidades de negócio

---

## Custo real das APIs

| Operação | API | Custo |
|---|---|---|
| Detecção de regiões protegidas | Claude Sonnet | ~6¢/imagem |
| Análise de peça (SEO) | Claude Sonnet | ~6¢/imagem |
| Geração SEO por plataforma | Claude Sonnet | ~3¢/plataforma |
| Variação de cor | Gemini Imagen | ~3¢/imagem |
| Remoção de fundo | rembg local | R$0,00 |
| Pipeline 4 views × 3 cores | Gemini + Claude | ~R$0,22 |

---

## Estado atual (Sprint 14)

**Implementado:** upload 4 views, remoção de fundo, detecção de regiões, variação de cor, aprovação/rejeição/archive, download ZIP, histórico completo, SEO (ML + Shopee + Shopify), rate limiting SEO, documentação completa.

**Pendente:** fundo alternativo lifestyle, vídeo UGC (KlingAI), multi-tenant SaaS.

---

## Comandos rápidos

```bash
docker compose up -d
docker compose exec api python -m pytest tests/ -v
docker compose exec api python backend/app/migrations/migrate_sprint_NN.py
docker compose logs api --tail=30
docker compose exec db psql -U confexai -d confexai_db
```
