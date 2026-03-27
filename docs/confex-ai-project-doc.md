# ConfexAI — Plataforma de Automação Visual para Confecção

> **Status:** Planejamento — MVP Interno (DRX Têxtil)  
> **Visão:** SaaS multi-tenant para confecções  
> **Última atualização:** 2026-03-26

---

## 1. Visão Geral

Empresas de confecção enfrentam custos recorrentes com fotografia, estúdio, modelo, maquiagem e tratamento de imagens. Além disso, há esforço manual significativo para renomear, padronizar, carregar imagens nas plataformas de e-commerce e escrever descrições otimizadas para SEO.

O **ConfexAI** automatiza esse fluxo completo: a partir de uma única foto da peça (sem fundo), o sistema gera variações de cor, fundos alternativos, descrições SEO-ready e vídeos no estilo UGC — prontos para upload no Mercado Livre, Shopee e loja própria.

---

## 2. Escopo do MVP

### 2.1 Funcionalidades

| Módulo | Descrição | API/Motor |
|---|---|---|
| **Remoção de fundo** | Isola a peça da imagem original | Gemini Vision / rembg |
| **Geração de descrição SEO** | Analisa a peça e gera título + descrição otimizados | Claude (Anthropic) |
| **Alteração de cor** | Recolore a peça mantendo textura, sombras e caimento | Gemini Imagen / KlingAI |
| **Fundo alternativo** | Fundo sólido ou temático (lifestyle) | Gemini Imagen |
| **Geração de vídeo UGC** | Reels estilo lifestyle/tendência com a peça | KlingAI |

### 2.2 Fora do escopo do MVP

- Publicação automática nas plataformas (upload será manual)
- Integração com SGP Costura
- Autenticação multi-tenant (SaaS)
- Geração de modelos virtuais vestindo a peça

---

## 3. Plataformas Alvo

| Plataforma | Formato de imagem | Vídeo aceito |
|---|---|---|
| Mercado Livre | JPG/PNG, mín. 500×500px, máx. 10MB | MP4 até 60s |
| Shopee | JPG/PNG, mín. 300×300px, máx. 2MB | MP4 até 60s |
| Loja própria (Shopify/VTEX) | Conforme configuração do tema | MP4 |

> **Convenção de saída:** todas as imagens geradas serão exportadas em **JPG 1200×1200px** (safe para todas as plataformas) e em **PNG com fundo transparente** para uso editorial.

---

## 4. Arquitetura Técnica

### 4.1 Stack

```
Backend:   FastAPI (Python 3.12)
Frontend:  React + Vite + TailwindCSS
Banco:     PostgreSQL 16
Container: Docker Compose
APIs ext.: Anthropic Claude, Google Gemini, KlingAI
```

> **Decisão de stack frontend:** React foi escolhido em vez de HTML/JS puro por três razões:
> 1. Gerenciamento de estado complexo (fila de imagens, progresso por etapa, variações)
> 2. Componentes reutilizáveis (card de produto, preview de cor, player de vídeo)
> 3. Escalabilidade para SaaS (auth, multi-tenant, dashboards)

### 4.2 Estrutura de Pastas

```
confex-ai/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── products.py       # CRUD de produtos
│   │   │   ├── images.py         # Upload, remoção de fundo, variações
│   │   │   ├── descriptions.py   # Geração SEO via Claude
│   │   │   └── videos.py         # Geração de vídeo via KlingAI
│   │   ├── services/
│   │   │   ├── background_removal.py
│   │   │   ├── color_variation.py
│   │   │   ├── seo_generator.py
│   │   │   └── video_generator.py
│   │   ├── models/               # SQLAlchemy ORM
│   │   ├── schemas/              # Pydantic
│   │   └── main.py
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   │   ├── Upload.jsx        # Tela de upload da peça
│   │   │   ├── ColorPicker.jsx   # Seleção de cores-alvo
│   │   │   ├── Results.jsx       # Galeria de resultados
│   │   │   └── Description.jsx   # Descrição SEO gerada
│   │   └── App.jsx
│   ├── Dockerfile
│   └── vite.config.js
├── docker-compose.yml
└── .env.example
```

### 4.3 Diagrama de Fluxo Principal

```
[Upload da foto original]
        ↓
[Remoção de fundo] → PNG transparente
        ↓
        ├──→ [Seleção de cores] → [Geração de variações de cor]
        ├──→ [Seleção de fundo] → [Composição final JPG]
        ├──→ [Análise da peça] → [Descrição SEO por plataforma]
        └──→ [Geração de vídeo UGC] → MP4
        ↓
[Download / Export de assets]
```

---

## 5. Módulos em Detalhe

### 5.1 Módulo de Descrição SEO

**Input:** imagem da peça (com ou sem fundo)  
**Output:** título + descrição por plataforma

**Campos gerados:**
- Título (máx. 60 chars para ML, 120 para Shopee)
- Descrição longa com: tipo de peça, modelagem, tecido, aviamentos relevantes, indicação de uso, cuidados de lavagem
- Tags/palavras-chave por plataforma
- Variações de cor listadas

**Motor:** Claude claude-sonnet-4-20250514 com visão (imagem + prompt estruturado)

---

### 5.2 Módulo de Alteração de Cor

**Input:** PNG da peça (fundo transparente) + lista de cores HEX ou nome  
**Output:** PNG da peça na(s) nova(s) cor(es)

**Requisitos de qualidade:**
- Manter textura do tecido visível
- Preservar sombras e caimento
- Não alterar botões, zípers, costuras em cor contrastante (a menos que especificado)

**⚠️ Restrição crítica — Estampas e Bordados:**
- Estampas, bordados, patches e aplicações decorativas **nunca mudam de cor**
- O sistema detecta automaticamente essas regiões via Claude Vision
- O operador revisa e ajusta as regiões protegidas antes de confirmar
- Ver seção 11 para detalhes da estratégia técnica

**Motor:** Gemini Imagen 3 (edit/inpaint com máscara) + Claude Vision (detecção de regiões protegidas)

**Fallback:** Se a cor resultante distorcer muito a textura, reprocessar com força de edição menor

---

### 5.3 Módulo de Fundo Alternativo

**Input:** PNG da peça (fundo transparente) + tipo de fundo desejado  
**Output:** JPG com fundo aplicado

**Tipos de fundo:**
- Cor sólida (HEX)
- Gradiente
- Temático lifestyle (ex: "loja boutique", "exterior urbano", "praia verão")

**Motor:** Gemini Imagen 3 (outpainting / composição)

---

### 5.4 Módulo de Vídeo UGC

**Input:** 1–5 imagens da peça (variações de cor/fundo) + briefing de estilo  
**Output:** MP4 ≤ 60s no formato Reels (9:16)

**Estilo padrão:** lifestyle/tendência — peça sendo mostrada em contexto real, movimento suave, paleta coerente com a marca

**Motor:** KlingAI (image-to-video ou text-to-video com referência de imagem)

---

## 6. Banco de Dados

### Entidades principais

```sql
products
  id, name, category, fabric, notes, created_at

product_images
  id, product_id, original_url, processed_url, type (original|color_variant|background|video)
  color_hex, background_type, platform_target, created_at

seo_descriptions
  id, product_id, platform (mercadolivre|shopee|shopify), title, description, tags, created_at

generation_jobs
  id, product_id, type, status (pending|processing|done|failed), api_used, cost_cents, created_at
```

---

## 7. Integrações Externas

### 7.1 Anthropic Claude
- **Uso:** análise de imagem + geração de descrição SEO
- **Modelo:** `claude-sonnet-4-20250514`
- **Autenticação:** `ANTHROPIC_API_KEY`

### 7.2 Google Gemini
- **Uso:** remoção de fundo, variação de cor, geração de fundo
- **Modelo:** `gemini-2.0-flash` (texto/visão) + `imagen-3.0` (geração de imagem)
- **Autenticação:** `GOOGLE_API_KEY`

### 7.3 KlingAI
- **Uso:** variação de cor avançada + geração de vídeo UGC
- **Autenticação:** `KLING_ACCESS_KEY` + `KLING_SECRET_KEY`
- **Docs:** https://klingai.com/api-reference

---

## 8. Variáveis de Ambiente

```env
# Banco
DATABASE_URL=postgresql://user:pass@db:5432/confexai

# APIs
ANTHROPIC_API_KEY=
GOOGLE_API_KEY=
KLING_ACCESS_KEY=
KLING_SECRET_KEY=

# App
UPLOAD_DIR=./uploads
OUTPUT_DIR=./outputs
MAX_IMAGE_SIZE_MB=20
DEFAULT_OUTPUT_FORMAT=jpg
DEFAULT_OUTPUT_RESOLUTION=1200
```

---

## 9. Roadmap

### Fase 1 — MVP Interno (DRX Têxtil)
- [ ] Setup Docker Compose (FastAPI + PostgreSQL + React)
- [ ] Upload de imagem + remoção de fundo
- [ ] Detecção de regiões protegidas (estampas/bordados) + revisão manual
- [ ] Geração de descrição SEO (Claude)
- [ ] Alteração de cor com máscara de proteção (Gemini)
- [ ] Fila de revisão/aprovação humana antes do export
- [ ] Tracking de custo por job
- [ ] Export de assets por plataforma

### Fase 2 — Consolidação
- [ ] Fundo alternativo (sólido + temático)
- [ ] Geração de vídeo UGC (KlingAI)
- [ ] Histórico de jobs com custo por geração
- [ ] Interface de revisão antes do export

### Fase 3 — Preparação SaaS
- [ ] Autenticação (JWT + multi-tenant)
- [ ] Billing por créditos
- [ ] API pública para integração com ERPs
- [ ] Integração com SGP Costura (base de produtos compartilhada)

---

## 10. Skills Claude necessárias para o projeto

As skills abaixo devem ser criadas no Claude Projects para auxiliar o desenvolvimento:

| Skill | Propósito |
|---|---|
| `confexai-architecture-decisions` | ADRs: React vs HTML, Gemini vs Replicate, estratégia de fila de jobs |
| `confexai-api-contracts` | Contratos de API (FastAPI), schemas Pydantic, convenções de endpoint |
| `confexai-image-pipeline` | Padrões para remoção de fundo, variação de cor, composição |
| `confexai-seo-prompts` | Prompts-padrão para geração de descrição por plataforma |
| `confexai-testing-standards` | Padrões de teste (similar ao SGP) |
| `confexai-sprint-workflow` | Workflow de desenvolvimento (similar ao SGP) |

---

## 11. Decisões Complementares

### Volume
- **MVP:** ~10 SKUs, 3–5 variações de cor por produto = até 50 imagens/ciclo
- **Escala SaaS:** volume ainda indefinido, mas a arquitetura deve suportar múltiplos tenants
- **Conclusão:** fila assíncrona (Celery + Redis) **não é necessária no MVP**, mas a estrutura de `generation_jobs` no banco já prepara a migração futura sem retrabalho

### Estampas e Bordados — Restrição Crítica
> ⚠️ **Esta é a regra de negócio mais importante do módulo de cor.**

Peças podem conter estampas, bordados ou aplicações decorativas que **não devem mudar de cor** junto com a peça base. O sistema precisa:

1. **Detectar regiões protegidas** na imagem (estampa, bordado, patch, botões decorativos)
2. **Mascarar essas regiões** antes de aplicar a variação de cor
3. **Recompor** a peça recolorida com as regiões protegidas preservadas

**Estratégia técnica:**
- Passo 1: Claude Vision analisa a imagem e identifica regiões protegidas → retorna coordenadas/máscara
- Passo 2: Gemini Imagen aplica inpainting **somente** na área mascarada da peça (excluindo regiões protegidas)
- Passo 3: Composição final combina peça recolorida + regiões originais preservadas

**Interface:** o operador poderá revisar e ajustar manualmente as regiões detectadas antes de confirmar a geração.

### Tracking de Custo por Job
Sim — `generation_jobs` incluirá `cost_cents` por operação. Custo estimado por operação:

| Operação | API | Custo estimado |
|---|---|---|
| Análise de imagem (SEO) | Claude | ~$0.01–0.03 |
| Variação de cor | Gemini Imagen | ~$0.02–0.04 |
| Fundo temático | Gemini Imagen | ~$0.02–0.04 |
| Vídeo UGC (60s) | KlingAI | ~$0.10–0.30 |

> Valores aproximados — serão calibrados com uso real no MVP.

### Aprovação Humana
Fluxo de aprovação **obrigatório** no MVP. Pipeline:

```
Geração → [Fila de Revisão] → Aprovação/Rejeição → Export
```

- Resultados rejeitados podem ser regenerados com parâmetros ajustados
- Aprovação registrada no banco com timestamp e usuário
- Automação completa como feature de Fase 3

### Marca d'água
Não será implementada no MVP.
```
