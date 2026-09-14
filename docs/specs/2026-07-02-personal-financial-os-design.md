# Personal Financial OS — Arquitetura & Roadmap

> Design aprovado em 2026-07-02. Ponto de partida: `~/lab/financas/`.

---

## Context

Você quer construir seu **principal software pessoal para os próximos 10 anos**: um
*Personal Financial Operating System* — não um dashboard, mas um sistema que aprende
sobre você via **memória estruturada** (nunca fine-tuning), roda **100% local**
(privacidade absoluta), e onde a LLM é **apenas uma interface substituível** — toda
lógica financeira é determinística (código, regras, SQL, estatística).

O sistema começa financeiro mas deve crescer em módulos (biblioteca, Kindle, saúde,
hábitos, projetos, carreira…). O princípio-mestre é **não reinventar o que já existe**.

### O que já existe (reusar, não recriar)
- **`~/lab/financas/importar.py`** — ETL CSV/OFX → SQLite com dedup por `fit_id`. É a
  semente do núcleo. **Correção obrigatória:** valores estão em `REAL` (float) — dinheiro
  jamais em float; migrar para inteiro em centavos ou `Decimal`.
- **`~/lab/agentes/`** — ecossistema Agno + Ollama + LanceDB já maduro (assistente, RAG,
  aprovação de comandos). A camada de IA se apoia nisto.
- **`~/lab/scripts/gpt-oss-server`** — llama.cpp com offload MoE (porta 8080).
- Docker + Compose 2.40, Ollama 0.21 com modelos 4–8B + `embeddinggemma`, Jellyfin.

### Restrição de hardware que define a arquitetura
12 cores, 32GB RAM (~18GB livres), **RTX 4060 Ti 8GB VRAM**, 297GB livres. 8GB de VRAM
limita a modelos 4–8B / contexto ~16K. **Consequência:** LLM fina + poucas tools não é
preferência, é imposição física. Todo cálculo pesado *tem* que ser determinístico. Isso
valida o princípio central do brief e reforça o veredito "modular monolith, não
microserviços".

---

## Princípios que travam decisões (não-negociáveis)

1. **LLM nunca calcula.** Patrimônio, saldos, parcelas, investimentos, projeções → só
   código determinístico. LLM traduz linguagem ↔ chamada de serviço e explica resultados.
2. **LLM atrás de uma porta (`AssistantPort`).** Trocar Ollama/qwen por outro modelo não
   pode tocar o domínio. As "tools" da LLM são os serviços do domínio expostos como funções.
3. **Dinheiro em inteiro (centavos) ou `Decimal`.** Nunca float. Nunca.
4. **Aprendizado = dados, não pesos.** Recategorizações, metas, decisões aceitas/ignoradas
   viram linhas em tabela e regras determinísticas. Zero fine-tuning.
5. **Modular monolith, não microserviços.** Single-user, RAM escassa → um processo, módulos
   como *bounded contexts* isolados. Microserviços custariam RAM e ops sem benefício.
6. **Reusar nas commodities, construir no domínio.** OCR/documentos/dashboards/vetores =
   projetos maduros. Ledger/regras/memória = código próprio (é pequeno e é onde você quer
   controle por 10 anos).
7. **Tudo substituível por trás de portas (Repository/Ports & Adapters).** Banco, LLM,
   dashboard, OCR, vetores — trocáveis sem tocar o núcleo.

---

## Decisões-chave confirmadas

| # | Decisão | Escolha | Por quê (curto) |
|---|---------|---------|-----------------|
| 1 | Núcleo do ledger | **Híbrido** (domínio próprio leve + commodities maduras) | Coerente com 8GB VRAM, código atual e longevidade. Adotar Firefly/Actual acoplaria seu "OS" ao schema deles por 10 anos. |
| 2 | Escopo do v1.0 (marco) | Importação + categorização **+ dashboard + chat + ingestão de documentos** (os 4 essenciais) | Você marcou os quatro como essenciais. São entregues incrementalmente em v0.1→v1.0; o marco v1.0 tem os quatro funcionando. |
| 3 | Investimentos | Manual/CSV agora; conectores (B3/corretoras) como **plugin** depois | Determinístico e simples primeiro; arquitetura já prevê expansão. |
| 4 | Local do projeto | **Evoluir `~/lab/financas`** | Reusa `importar.py`, `extratos/`, `db/` e o ecossistema `~/lab` (agentes, mirrors, `sync-lab.sh`). |

---

## Arquitetura

### Forma geral: Modular Monolith + Clean Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  INTERFACES (adapters de entrada)                                 │
│  • REST API (FastAPI + OpenAPI auto)   • CLI (evolui p/ Typer)    │
│  • Chat (AssistantPort → Agno/Ollama)  • Dashboard (Metabase)     │
├─────────────────────────────────────────────────────────────────┤
│  APPLICATION (casos de uso / serviços) — orquestra, sem regra HTTP│
│  ImportarExtrato · Categorizar · CalcularPatrimonio ·            │
│  ProjetarFluxo · AvaliarCompra · ConsultarReserva · ...          │
├─────────────────────────────────────────────────────────────────┤
│  DOMAIN (puro Python, zero framework)                            │
│  Entidades: Conta, Transacao, Categoria, Regra, Meta, Reserva,  │
│  Orcamento, Parcela, Ativo, Posicao · Value Objects: Dinheiro   │
│  (centavos), Periodo · Serviços de domínio · Eventos            │
├─────────────────────────────────────────────────────────────────┤
│  INFRASTRUCTURE (adapters de saída — portas implementadas)       │
│  Repositórios (SQLAlchemy/Postgres) · AssistantPort (Agno) ·     │
│  OCRPort (Docling) · DocStorePort (Paperless) · VectorPort       │
│  (LanceDB) · CotacaoPort (API pública) · EventBus (in-proc)      │
└─────────────────────────────────────────────────────────────────┘
```

O **DOMAIN** não importa nada de fora. A **APPLICATION** depende só de *ports* (interfaces).
A **INFRASTRUCTURE** implementa as ports. Trocar qualquer tecnologia = trocar um adapter.

### Kernel compartilhado (o que todos os módulos futuros herdam)
- **Identity** (single-user, mas modelado como usuário para futuro).
- **EventBus** in-process (publica `TransacaoImportada`, `MetaAtingida`…).
- **DocumentStore** (Paperless-ngx) — documentos de qualquer módulo.
- **AssistantPort** — a interface conversacional, uma só para todos os módulos.
- **MemoryStore** — memória estruturada de longo prazo (tabelas + índice vetorial).
- **ModuleRegistry** — cada módulo se registra: expõe serviços à API e *tools* ao assistente.

### Contrato de módulo (escalabilidade para biblioteca/saúde/hábitos…)
Cada módulo futuro é um *bounded context* que implementa:
```
class Module(Protocol):
    name: str
    def routers(self) -> list[APIRouter]        # endpoints REST
    def tools(self) -> list[AssistantTool]       # funções determinísticas p/ a LLM
    def migrations(self) -> Path                 # schema próprio
    def subscribe(self, bus: EventBus) -> None   # reage a eventos de outros módulos
```
Assim, adicionar "biblioteca" ou "saúde" em 2028 = novo pacote que implementa `Module`,
**sem tocar** finanças. Kernel estável, módulos plugáveis.

---

## Stack escolhida (com crítica: por quê · alternativas descartadas · riscos · manutenção · comunidade · migração)

### Linguagem & núcleo — **Python 3.12** + domínio puro
- **Por quê:** já é sua stack (Agno, TCC, importar.py); ecossistema de dados/OCR/ML
  incomparável; Pydantic/SQLAlchemy maduros.
- **Alternativas descartadas:** Go/Rust (melhor performance/binário único, mas você perde
  todo o ecossistema de IA local e produtividade — over-engineering para single-user);
  TypeScript/Node (bom, mas duplica linguagem vs. seus agentes Python).
- **Riscos:** performance de cálculo pesado → mitigado com DuckDB/SQL para agregações.
- **Manutenção/comunidade:** máxima. **Migração:** domínio puro isola de qualquer troca.

### API — **FastAPI**
- **Por quê:** REST + **OpenAPI/Swagger automático** (requisito seu), async, validação
  Pydantic nativa, docs vivas.
- **Descartadas:** Flask (sem docs/tipos nativos), Django REST (traz ORM/admin pesados que
  brigam com Clean Arch), Litestar (ótimo, mas comunidade menor).
- **Riscos:** baixo; projeto muito ativo. **Migração:** rotas são adapters finos.

### Contratos — **Pydantic v2**
- Já usado no seu TCC; validação forte na borda; serializa DTOs. Comunidade enorme.

### Banco (system of record) — **PostgreSQL** (via Docker) + **SQLAlchemy** + **Alembic**
- **Por quê:** confiável por décadas, JSONB (metadados flexíveis por módulo), extensões
  (pgvector no futuro), migrações versionadas com Alembic. SQLAlchemy isola o SQL do domínio.
- **Estratégia de transição:** **v0.1 usa o SQLite atual** (mais rápido para você já usar);
  **v0.2 migra para Postgres** — como o acesso é via repositórios SQLAlchemy, a migração é
  trocar a connection string + rodar Alembic. Migração barata *por construção*.
- **Descartadas:** ficar em SQLite para sempre (limita concorrência/múltiplos módulos);
  MySQL (JSONB/extensões inferiores); MongoDB (finanças são relacionais, não documento).
- **Riscos:** um container a mais (~150MB RAM) — aceitável. **Comunidade/atualizações:**
  entre os projetos mais estáveis do mundo.

### Analytics/consultas — **DuckDB** (embutido, sob demanda)
- **Por quê:** OLAP colunar in-process, lê Postgres/Parquet, agregações pesadas
  (heatmaps, séries históricas, projeções) em milissegundos — **sem** servidor extra.
  Substitui "cálculo pela LLM" por SQL analítico rápido.
- **Descartadas:** ClickHouse (servidor pesado, overkill single-user); Pandas puro (pior
  em datasets grandes e menos "SQL declarativo").
- **Riscos:** baixo; projeto muito ativo. **Migração:** é uma lib, removível.

### Dinheiro — **inteiro em centavos** (Value Object `Dinheiro`) + `Decimal` nas fronteiras
- Corrige o bug do `importar.py` (float). Padrão contábil. Zero dependência.

### OCR / extração de documentos — **Docling**
- **Por quê:** extração layout-aware de PDF/tabelas/imagens, moderna, boa para recibos e
  documentos estruturados; roda local.
- **Insight BR:** **NF-e é XML** (DANFE). Quando houver XML, **parsear XML direto
  (determinístico)** — nada de OCR. OCR só para papel/imagem sem dado estruturado.
- **Descartadas:** Tesseract puro (só OCR bruto, sem layout — mas fica *dentro* do
  Paperless como engine); Apache Tika (extração genérica, menos preciso em tabelas);
  Unstructured.io (bom, licença/complexidade maiores).
- **Riscos:** projeto novo (IBM) — mitigar isolando atrás de `OCRPort` (trocável por Tika).
  **Comunidade:** crescendo rápido. **Migração:** fácil (é uma port).

### Gestão documental — **Paperless-ngx**
- **Por quê:** dedup, metadados, full-text, tags, OCR (Tesseract), inbox automático,
  API REST. Resolve "organizar documentos / eliminar duplicidades / criar metadados" sem
  escrever nada. Comunidade enorme, altíssima atividade.
- **Descartadas:** construir gestor próprio (viola "não reinventar"); Mayan EDMS (mais
  pesado/corporativo); Docspell (bom, comunidade menor).
- **Riscos:** container a mais; acoplamento leve → isolar atrás de `DocStorePort`.
- **Uso:** Paperless guarda o arquivo; nosso domínio guarda o **vínculo documento↔transação**.

### IA local — **Ollama** (já rodando) + **`embeddinggemma`**
- **Por quê:** já instalado, API simples, troca de modelo trivial. Mantém a LLM
  substituível de fato.
- **Descartadas:** llama.cpp direto (você já tem o `gpt-oss-server` como *fallback*/modelos
  MoE; Ollama é o default por ergonomia); vLLM (VRAM insuficiente).
- **Risco:** 8GB VRAM → usar 4–8B; nunca depender da LLM para números.

### Orquestração do chat — **Agno** (thin) atrás de `AssistantPort`
- **Por quê:** já é sua stack; leve; tool-calling com poucas tools (ideal p/ modelo local).
  As tools são funções determinísticas do domínio (ex.: `avaliar_compra(valor)` retorna o
  cálculo pronto; a LLM só verbaliza).
- **Descartadas para ESTE módulo:** LangGraph (é a escolha certa do seu TCC para grafos de
  agentes complexos, mas aqui seria over-engineering — consultor financeiro precisa de um
  loop ReAct simples com ~6 tools). n8n (automação de fluxos, não conversação — pode entrar
  depois para *ingestão agendada*, não para o chat).
- **Substituibilidade:** o contrato é `AssistantPort`; Agno é um adapter. Trocável por
  chamada Ollama crua, LangGraph, ou outro — sem tocar domínio.

### Memória vetorial / RAG — **LanceDB** (embutido)
- **Por quê:** **embedded** (sem container extra — crucial p/ sua RAM), já usado nos seus
  agentes, colunar, filtros + vetores. Guarda recall semântico de contexto (histórico de
  conversas, notas), **nunca** números críticos.
- **Descartadas:** **Qdrant** (excelente, mas é um servidor a mais — fica como *caminho de
  scale-up* documentado se o volume crescer); **Chroma** (mais simples que Qdrant porém
  menos robusto/performático que LanceDB embarcado); pgvector (viável, mas mistura busca
  vetorial no Postgres transacional — prefiro isolar).
- **Migração:** atrás de `VectorPort` → trocar por Qdrant = um adapter.

### Dashboard — **Metabase** (v1) atrás de conexão só-leitura
- **Por quê:** dashboards ricos sobre SQL sem escrever front-end; conecta em
  Postgres/DuckDB; exploração ad-hoc ("o que mudou nos meus gastos?"); self-host Docker.
- **Descartadas:** **Grafana** (excelente para séries temporais/métricas, mas menos natural
  para exploração financeira business — pode complementar depois para "calendário
  financeiro"); **Superset** (mais poderoso, porém pesado e mais ops); front-end custom
  (Next.js) → **YAGNI agora**; entra só se o Metabase apertar (v1.x+).
- **Risco:** licença Metabase (AGPL/enterprise) — a edição community atende; verificar na
  implementação. **Migração:** dashboards são camada de leitura, descartável.

### Deploy — **Docker Compose**
- Serviços: `postgres`, `api` (FastAPI), `paperless-ngx`, `metabase`. **Ollama fica no host**
  (já roda, evita configurar GPU duas vezes) — a `api` fala com ele via host. DuckDB/LanceDB
  são embarcados (sem container). Baixo consumo, containers independentes, um comando p/ subir.

### Qualidade — **pytest** + **ruff** + **mypy** + **GitHub Actions**
- Domínio testável isoladamente (é puro). CI roda testes/lint. Docs OpenAPI automáticas.

---

## Modelo de dados & memória estruturada

**Núcleo financeiro** (evolui o schema atual):
- `contas`, `transacoes` (com `fit_id` dedup — reusar), `categorias`, `regras_categorizacao`,
  `orcamentos`, `metas`, `reservas`, `parcelas`, `ativos`, `posicoes`, `cotacoes`.
- `documentos` (id Paperless) + `documento_transacao` (vínculo N:N).

**Memória de longo prazo (o "aprendizado"):**
- `preferencias` (categorias suas, prioridades, sazonalidades declaradas).
- `regras` — quando você recategoriza, nasce/ajusta uma regra determinística → a
  categorização melhora sozinha, **sem** treinar modelo.
- `decisoes` — recomendações **aceitas vs. ignoradas** (ex.: "sugeri cortar X, você ignorou").
- `padroes` — padrões de gasto derivados por estatística (média móvel, desvio, sazonal).
- `memorias` — notas semânticas indexadas no LanceDB para recall conversacional.

**Regra de ouro:** a LLM lê a memória para *contexto/tom*; os **números** vêm sempre de
SQL/serviços.

---

## Fluxos principais

### Ingestão (determinística primeiro)
1. Arquivo cai em `extratos/` (ou inbox do Paperless para PDFs/imagens).
2. OFX/CSV/XLSX → parser determinístico → `transacoes` (dedup por `fit_id`).
3. PDF/imagem → Docling/Paperless → metadados; NF-e XML → parser XML direto.
4. Categorização: **regras determinísticas primeiro**; só o resíduo vai à LLM para
   *sugestão* (que você confirma → vira regra).

### Chat consultor ("Posso comprar esse Kindle?")
1. LLM interpreta intenção → escolhe uma tool (ex.: `avaliar_compra`).
2. **Serviço determinístico** calcula: saldo projetado, impacto na reserva, orçamento da
   categoria, parcelas futuras → retorna veredito + números.
3. LLM **apenas verbaliza** o resultado com o histórico/memória como contexto.
   Se a LLM sumir amanhã, os serviços continuam respondendo via API/CLI.

---

## Roadmap (versões, cada uma utilizável)

**v0.1 — Núcleo utilizável (SQLite)**
Evoluir `importar.py`: corrigir dinheiro (centavos), estruturar domínio (Clean Arch),
importar OFX/CSV/XLSX com dedup, categorização por regras, CLI de consultas.
*Verificar:* importar seus extratos reais; `pytest` do domínio verde; "maiores gastos de junho" via CLI.

**v0.2 — Postgres + API + Dashboard**
Migrar SQLite→Postgres (Alembic), subir FastAPI (OpenAPI), Metabase em Docker Compose.
Dashboard: patrimônio, fluxo, categorias, parcelas futuras.
*Verificar:* `docker compose up` sobe tudo; dashboard mostra dados reais; `/docs` navegável.

**v0.3 — Chat consultor**
`AssistantPort` + Agno/Ollama, ~6 tools determinísticas (avaliar_compra, quanto_posso_gastar,
saude_reserva, evolucao_patrimonial…). Memória estruturada (regras, decisões, padrões).
*Verificar:* respostas batem com os números do dashboard; desligar Ollama → API ainda responde.

**v0.4 — Documentos & OCR**
Paperless-ngx + Docling; inbox de PDFs/imagens; NF-e XML; vínculo documento↔transação.
*Verificar:* jogar uma nota fiscal → aparece vinculada à transação certa.

**v0.5 — Investimentos (manual/CSV)**
`ativos`/`posicoes`/`cotacoes`; aportes manuais/CSV corretora; cotações via API pública;
patrimônio consolidado (caixa + investimentos).
*Verificar:* posição e evolução patrimonial corretas vs. cálculo manual.

**v1.0 — Consolidação**
Projeções (fluxo futuro, sazonalidade), calendário financeiro, heatmaps, alertas por
regra (reserva baixa, estouro de orçamento), backups automatizados.
*Verificar:* uso diário por 2 semanas sem cair para planilha.

**Além do v1 (plataforma):** `ModuleRegistry` + contrato de módulo; primeiro módulo
não-financeiro (biblioteca/Kindle — você já tem `kindle-auto/` e usa Calibre) como prova do
plugin architecture; conectores de investimento (B3/corretora) como plugins; Qdrant se o
volume vetorial crescer.

---

## Riscos & mitigações
- **Over-engineering** (o maior risco de um "OS"): mitigado por YAGNI + versões utilizáveis +
  modular monolith. Nada de microserviços/CQRS/event-sourcing sem necessidade comprovada.
- **Acoplamento a projetos de terceiros:** tudo atrás de ports (OCR, DocStore, Vector,
  Assistant, Cotação) → trocável.
- **Dinheiro em float:** corrigido no v0.1 (Value Object em centavos).
- **Dependência da LLM:** proibida por construção; API/CLI funcionam sem modelo.
- **Docling ser novo:** isolado atrás de `OCRPort`; fallback Tika/Tesseract.

## Verificação end-to-end (critério de sucesso global)
Em cada versão: (1) `pytest` do domínio verde; (2) `docker compose up` sobe o stack;
(3) uma pergunta real respondida com número que bate com cálculo manual; (4) LLM desligada →
sistema ainda responde via API/CLI (prova de substituibilidade).

---

## Pendências (resolver na fase de implementação, não bloqueiam o design)
1. **Bancos que você usa** (parsers de import): Nubank já mapeado — quais mais? (definimos ao escrever o v0.1)
2. **Metabase community vs Grafana** para o "calendário financeiro": default = Metabase; revisitar no v0.2.
