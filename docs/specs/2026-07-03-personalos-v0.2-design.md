# PersonalOS v0.2 — Revisão de Arquitetura & Roadmap da Plataforma

> Substitui o escopo "v0.2 = Postgres + API + Dashboard financeiro" do design original
> (`2026-07-02-personal-financial-os-design.md`). Aprovado em 2026-07-03.

---

## Context

O usuário pivotou a visão do projeto: não é mais "sistema financeiro com dashboard", é **PersonalOS** — plataforma pessoal local, modular, para 10 anos, onde finanças é o primeiro módulo de muitos (biblioteca, projetos, saúde, serviços do computador…). Antes de qualquer código, ele pediu revisão crítica de toda a arquitetura proposta.

Dois arquitetos independentes analisaram o pivot (um YAGNI-minimalista projetando o kernel mínimo viável, um crítico de sobrevivência de 10 anos estress-testando as 7 propostas do usuário), complementados por três explorações de contexto (repositórios anteriores, decisões já registradas, e a reusabilidade real do código v0.1 como kernel). Este documento é a síntese arbitrada dessas perspectivas.

### Fatos que fundamentam as decisões
- **v0.1 estava pronto e não-mergeado** (branch `financas-v0.1`, 45 testes, ruff/mypy limpos) — já mergeado na `main` como pré-requisito deste v0.2.
- **v0.1 usa Clean Arch folder-per-layer DENTRO de um módulo** — precisa inverter para package-per-module para caber um segundo módulo.
- **Colisão de namespace é real**: `MetaData` global com tabelas sem prefixo (`transacoes`, `regras`); SQLite não tem schemas.
- **`vw_saldo` (proposta original do usuário) é matematicamente incalculável hoje**: não existe tabela `contas` com saldo inicial — somar transações só dá saldo real se importou desde a abertura da conta.
- **Backup era inexistente** e o banco vira registro financeiro crítico — gap grave da proposta original.
- **Embed interativo do Metabase é feature paga** na edição OSS (likely — a confirmar na implementação); static embed/link público é o que está disponível de graça.
- **Padrões do próprio usuário pra reusar**: `kindle-sys` (seu repo — formato de módulo: CLI + config XDG TOML + providers plugáveis), `atende-ai` (seu repo — conteúdo YAML + engine fixo auditável, mas só compensa com muitas regras homogêneas), monorepo `~/lab`, SolidJS/Next.js como zona de conforto de UI (rejeitados aqui por custo de manutenção de década; porta de saída documentada caso o HTMX se mostre insuficiente).

### Decisões travadas com o usuário
| Decisão | Escolha |
|---|---|
| Merge v0.1 antes do v0.2 | **Sim** — feito (`main`, commit `295fd72`) |
| Banco | **SQLite + WAL + prefixo por módulo** (Postgres com gatilho documentado, não descartado) |
| Dashboard | **FastAPI + Jinja2 + HTMX** servido pelo mesmo processo da API |
| Local do código | **`~/lab/personalos/`** (rename de `financas/`, git mv preservando história) |
| Modelo de execução | Subagentes implementadores em **Sonnet**; revisões críticas no modelo principal |

### Arbitragem das 7 propostas do usuário
| Proposta original | Veredito | Forma final adotada |
|---|---|---|
| v0.2 = Plataforma (API+Analytics+Dashboard+Core) | Aceita, versão mínima | Kernel = manifesto de dados (dataclass), não framework. Sem EventBus, sem registry dinâmico/discovery — lista estática de módulos (`nucleo/registro.py`). |
| Analytics = views SQL versionadas | Aceita com cortes | ~7 views `vw_financas_*_v1`. Corta `vw_metricas` (anti-padrão "gaveta de tudo, sem grão definido"); `vw_evolucao_reserva` vira `vw_financas_saldo_acumulado_v1` (derivado via window function; comparação com meta fica no insight, não na view). Testes de paridade view×Python obrigatórios pras consultas legadas. |
| Dashboard próprio, Metabase rebaixado a ferramenta | Aceita, ultra-fino | HTMX server-rendered no mesmo processo da API (zero toolchain JS pra manter por 10 anos), contrato `CardResumo` por módulo, seções vazias ocultas (Chat/Documentos/Atividades até existirem de verdade), assets vendorizados. Metabase vira `compose.yaml` opcional (profile) + deep-links, não mais "o dashboard". |
| Memory Engine antes da LLM | Aceita, mínimo | 2 tabelas (`nucleo_memoria`, `nucleo_insights`), não um schema de 9 tabelas especulativas. Tipos de conhecimento (metas, preferências, decisões, hábitos...) são linhas JSON tipadas por Pydantic no ponto de uso; promover a tabela dedicada só sob pressão real de consulta/relação. |
| Insights determinísticos por regras | Aceita | 2–3 regras Python hardcoded por módulo → tabela com dedup (`UNIQUE(regra_id, chave_dedup)`) e status (novo/visto/dispensado). YAML de regras (padrão `atende-ai`) só entra com >10 regras — virar DSL pra 3 regras heterogêneas seria overengineering. |
| Porta `ChatService` (stub) agora | Aceita | `ServicoChat` Protocol + `ChatIndisponivel` (levanta erro claro / responde 501 na API). Justificado porque `/api/chat` e a seção Chat do painel **tocam** a porta já no v0.2 — não é código morto. |
| Porta `PriceProvider` agora | Só o Protocol, sem stub | Nada consome preços no v0.2; declarar um stub seria código morto. O Protocol documenta a intenção e o mypy valida quando o primeiro adapter nascer. Risco registrado: scraping quebra com frequência e esbarra em ToS — se um dia existir, é plugin de módulo, nunca contrato de kernel. |

### O que o usuário não propôs e entra mesmo assim
1. **Backup automatizado + teste de restore** desde o v0.2.0 — `sqlite3 .backup` diário + destino externo, com os extratos brutos originais preservados como disaster-recovery idempotente (reimportação via `fit_id` é segura por construção, herdada do v0.1).
2. **`financas_contas` com saldo inicial** — pré-requisito matemático de uma `vw_saldo` correta.
3. **Mini-mecanismo de migração** (`nucleo_migracoes` + passos idempotentes, ~30 linhas). Alembic explicitamente adiado com gatilho: primeira mudança destrutiva de schema que o mini-mecanismo torne desconfortável.

---

## Arquitetura alvo

```
~/lab/personalos/
├── pyproject.toml                  # name="personalos"; +fastapi, uvicorn, jinja2
├── extratos/                       # inbox de importação (inalterado do v0.1)
├── compose.yaml                    # SÓ metabase, profiles: [metabase]
├── src/personalos/
│   ├── cli.py                      # Typer raiz: add_typer(financas) + insights, memoria, servir, backup
│   ├── nucleo/                     # kernel INTEIRO — ~7 arquivos pequenos, sem framework de plugin
│   │   ├── config.py               # XDG: ~/.config/personalos/ + ~/.local/share/personalos/personalos.db
│   │   ├── db.py                   # criar_engine (WAL, busy_timeout, FKs), aplicar_schema, aplicar_vistas
│   │   ├── migracoes.py            # nucleo_migracoes + passos idempotentes
│   │   ├── modulo.py               # dataclasses: Modulo, CardResumo, RegraInsight, Insight, Vista
│   │   ├── registro.py             # MODULOS: tupla ESTÁTICA de manifestos
│   │   ├── memoria.py              # nucleo_memoria (JSON tipado por Pydantic no ponto de uso)
│   │   ├── insights.py             # motor: itera MODULOS, roda regras, INSERT OR IGNORE (dedup)
│   │   └── portas/
│   │       ├── chat.py             # ServicoChat Protocol + ChatIndisponivel
│   │       └── precos.py           # ProvedorPrecos Protocol + Oferta (só isso, sem stub)
│   ├── modulos/financas/
│   │   ├── dominio/                # dinheiro, modelos, categorizador — intactos do v0.1
│   │   ├── aplicacao/              # portas, importar, consultas — intactos, imports ajustados
│   │   ├── infra/                  # tabelas.py (MetaData próprio, prefixo financas_), repositorios, leitores/
│   │   ├── analytics/vistas.py     # VISTAS _v1 (DDL em Python, recriadas na inicialização — sem Alembic)
│   │   ├── insights.py             # regras determinísticas do módulo
│   │   ├── api.py                  # APIRouter → montado em /api/financas
│   │   ├── cli.py                  # sub-Typer (mesmos comandos do v0.1, sem bootstrap de engine)
│   │   └── modulo.py               # MODULO = Modulo(...)  — o manifesto
│   ├── api/app.py                  # criar_app(): saúde, insights, memoria, chat(501), routers de módulos, painel
│   └── painel/                     # rotas.py + templates/ (Jinja) + static/ (htmx/chart.js vendorizados)
└── tests/                          # 45 migrados do v0.1 + paridade_vistas, memoria, insights, api, cli
```

### Contrato de módulo
Dados, não métodos — o "registry" inteiro é um `for m in MODULOS: ...` no kernel:
```python
@dataclass(frozen=True)
class Modulo:
    nome: str                                    # vira prefixo de tabela e de rota
    metadata: MetaData                           # tabelas do módulo (prefixadas)
    vistas: tuple[Vista, ...] = ()               # DDL das views analíticas versionadas
    cli: typer.Typer | None = None               # sub-app → `personalos <nome> ...`
    router: APIRouter | None = None              # montado em /api/<nome>
    card: Callable[[Engine], CardResumo] | None = None   # card no Resumo Geral
    regras_insights: tuple[RegraInsight, ...] = ()
```
Um módulo futuro (`modulos/biblioteca/`) é um diretório irmão com a mesma forma + uma linha em `registro.py`. O padrão do `kindle-sys` (CLI + config TOML XDG + providers plugáveis) encaixa direto nessa forma quando chegar a hora.

### Camada de Analytics (views SQL)
Views em dialeto SQLite, sufixo `_v1`, sempre expondo `*_centavos` (nunca float):
`vw_financas_saldo_v1` (saldo inicial de `financas_contas` + soma de transações), `vw_financas_fluxo_mensal_v1`, `vw_financas_gastos_categoria_v1`, `vw_financas_receitas_v1`, `vw_financas_despesas_v1`, `vw_financas_maiores_gastos_v1`, `vw_financas_saldo_acumulado_v1` (window function `SUM(...) OVER (ORDER BY data, fit_id)`, por transação individual — não por mês).

Mecanismo: `nucleo/db.py::aplicar_vistas(engine)` roda `DROP VIEW IF EXISTS` + `CREATE VIEW` pra cada vista de cada módulo, na inicialização (CLI e API) — views não têm dados próprios, recriar sempre é barato e elimina bookkeeping de "view desatualizada".

**Versionamento = contrato de mudança:** alterar a lógica de uma view publicada cria `_v2` mantendo `_v1` até os consumidores migrarem — isso é o que isola dashboards da evolução do schema, não cerimônia.

**Anti-drift (view × `aplicacao/consultas.py`):**
- Consultas legadas (`saldo`, `maiores_gastos`, `gastos_por_categoria`) continuam em Python (código testado) + teste de paridade obrigatório (`test_paridade_vistas.py`: mesmo banco semeado, asserta `consultas.f(repo) == SELECT * FROM vw_financas_*_v1`). Drift = build vermelho.
- Consultas novas (fluxo mensal, receitas, despesas, saldo acumulado) nascem view-first — a função Python correspondente vira um leitor fino da view. Sem duplicação, sem paridade a manter.

### Memória e Insights
```sql
nucleo_memoria (
  id INTEGER PK, modulo TEXT NOT NULL, tipo TEXT NOT NULL,   -- meta|preferencia|decisao|padrao|habito...
  chave TEXT NOT NULL, valor TEXT NOT NULL,                   -- JSON
  atualizado_em TEXT NOT NULL,
  UNIQUE(modulo, tipo, chave)
)
nucleo_insights (
  id INTEGER PK, modulo TEXT, regra_id TEXT NOT NULL,
  chave_dedup TEXT NOT NULL,                                  -- ex: "alimentacao:2026-07"
  titulo TEXT, detalhe TEXT,                                  -- JSON com os números
  severidade TEXT, status TEXT DEFAULT 'novo',                -- novo|visto|dispensado
  criado_em TEXT,
  UNIQUE(regra_id, chave_dedup)
)
```
"Histórico de recomendações aceitas/ignoradas" = o próprio `nucleo_insights.status`. Regra = função Python testável (`RegraInsight(id, avaliar: Callable[[Engine], list[Insight]])`), determinística, lê views + memória. Disparo: chamada direta ao fim de `personalos financas importar` (o "evento" do v0.2 — sem EventBus) + `personalos insights gerar` sob demanda. Regras do v0.2: `reserva_abaixo_da_meta`, `categoria_acima_da_media_6m`.

### API
FastAPI, bind `127.0.0.1`, sem auth (single-user local), `personalos servir`:
```
GET  /api/saude
GET  /api/financas/{saldo,gastos,categorias,fluxo-mensal}
GET  /api/insights?modulo=&status=      PATCH /api/insights/{id}/status
GET  /api/memoria/fatos?modulo=&tipo=   PUT  /api/memoria/fatos
POST /api/chat                          → 501 Not Implemented (via ChatIndisponivel)
GET  /docs                              → OpenAPI de graça
GET  /                                  → painel (Jinja)
```

### Dashboard (painel)
FastAPI + Jinja2 + HTMX no mesmo processo da API — zero toolchain Node pra apodrecer em 10 anos, zero RAM extra. Rota do Resumo Geral itera `MODULOS`, chama `m.card(engine)` de quem tem card, renderiza um template genérico. Seções pedidas pelo usuário (Resumo Geral → Gráficos → Chat → Documentos → Atividades) existem no template; **Chat mostra placeholder "em breve (v0.3)"**, Documentos/Atividades ficam ocultas até existir dado real. Gráficos via Chart.js (vendorizado) sobre os endpoints da API. Metabase = deep-link ("Explorar no Metabase"), não iframe embutido (interactive embed é pago na OSS).

---

## Roadmap v0.2.x (cada versão utilizável)

| Versão | Entrega | Utilizável = |
|---|---|---|
| **pré** ✅ | Merge `financas-v0.1` → `main` | Feito — commit `295fd72`, 45 testes verdes na main |
| **v0.2.0 — Replatform + Fundação** ✅ | Rename `personalos/` (git mv, commits só-rename), package-per-module, `nucleo/{config,db,migracoes,modulo,registro}`, prefixos de tabela + migração 001, WAL/XDG, CLI raiz, **backup automatizado com restore testado** | `personalos financas saldo` == v0.1 sobre o DB real migrado; 45 testes verdes; backup rodando |
| **v0.2.1 — Domínio + Analytics** ✅ | `financas_contas` (saldo inicial) + CLI, views `_v1` + testes de paridade, `personalos financas fluxo`, Metabase opcional (compose profile, read-only) | Saldo CORRETO (não mais aproximado); fluxo mensal no terminal; Metabase plota sobre as views |
| **v0.2.2 — API** ✅ | FastAPI (`criar_app`), endpoints financas + saúde + chat 501, `personalos servir` | `/docs` navegável; números da API batem com a CLI; desligar tudo → CLI segue |
| **v0.2.3 — Painel** ✅ | Jinja+HTMX: Resumo Geral com cards, gráficos Chart.js, deep-link Metabase, placeholders Chat/seções vazias ocultas | `localhost:8000` mostra o PersonalOS real com dados reais |
| **v0.2.4 — Memória + Insights** ✅ | `nucleo_memoria`/`nucleo_insights`, `personalos memoria definir-meta`, 2–3 regras, insights no painel/CLI, `ProvedorPrecos` Protocol | Definir meta → insight aparece no dashboard, some ao dispensar |

> **Situação em 09/08/2026:** o roadmap inteiro (v0.2.0 … v0.2.4) está entregue e
> mergeado na `main`, até o commit `03bd600`. Duas divergências deliberadas em
> relação ao planejado aqui: o painel saiu **sem HTMX e sem Chart.js** — HTML puro e
> gráfico SVG gerado no servidor (ADR 0007) —, e o endpoint de chat continua sem
> consultor: `nucleo/portas/chat.py` define o contrato e painel e API já o consomem,
> mas nenhuma implementação foi escrita. Entregas fora do roadmap vieram junto:
> leitor de extrato em PDF com reconciliação, `sugerir-regras`/`recategorizar` e as
> perguntas de decisão (`custo-basico`, `onde-cortar`, `pode-comprar`, `projecao`).

**Gatilhos documentados para revisitar decisões (manter no README do repo):**
- Alembic ← primeira migração destrutiva de schema desconfortável pro mini-mecanismo.
- Postgres ← necessidade real de 2º processo escritor concorrente, ou pgvector.
- EventBus ← primeiro par publicador/assinante real entre dois módulos distintos.
- YAML de regras de insight ← quando passarem de ~10 regras.
- SPA (SolidJS) no lugar do painel HTMX ← dores documentadas de verdade com HTMX, não antecipação.
- Reavaliar embed do Metabase ← se o deep-link se mostrar insuficiente na prática.

---

## Addendum — decisões de implementação do v0.2.1 (Domínio + Analytics)

Decisões que a spec original deixou em aberto, fechadas agora (critério: menor mudança que resolve o problema real, revisável depois):

- **`financas_contas`**: `Table("financas_contas", Column("nome", String, primary_key=True), Column("saldo_inicial_centavos", BigInteger, nullable=False, default=0))`. Não vira FK de `financas_transacoes.conta` (que continua string livre) — a view `vw_financas_saldo_v1` soma duas subqueries independentes (`SUM` de `financas_transacoes` + `SUM` de `saldo_inicial_centavos` em `financas_contas`, cada uma com `COALESCE(..., 0)`), então contas sem saldo inicial declarado continuam se comportando como hoje (soma pura das transações). Comando novo: `personalos financas conta <nome> <saldo_inicial>` (upsert).
- **`Vista` (dataclass do kernel)**: `Vista(nome: str, sql: str)`. Vira o 4º campo de `Modulo` (`vistas: tuple[Vista, ...] = ()`), adicionado agora porque v0.2.1 é a primeira fatia que efetivamente usa views — mesma disciplina do v0.2.0 (campo nasce quando alguém o usa, não antes).
- **`aplicar_vistas`**: mora em `nucleo/db.py`, mesma assinatura por parâmetro que `criar_engine` já usa pra `metadatas` (evita reintroduzir o import circular já resolvido no v0.2.0) — `aplicar_vistas(engine, vistas: Sequence[Vista])`, chamada de dentro de `criar_engine` logo após `metadata.create_all`.
- **Metabase (`compose.yaml`)**: serviço único, profile `metabase`, bind mount **read-only** do arquivo SQLite real (`~/.local/share/personalos/personalos.db:/data/personalos.db:ro`), volume próprio pro app-db interno do Metabase (H2). Conexão ao SQLite configurada manualmente pela UI do Metabase no primeiro acesso (não hardcoded via env var) — é passo único, aceitável pra ferramenta opcional de uso pessoal.

---

## Riscos aceitos & mitigações
1. **Kernel desenhado com n=1 módulo ossifica errado.** Mitigação: contrato é uma dataclass de dados (barato de mudar depois), não uma hierarquia de classes; revisão obrigatória do contrato quando o módulo `biblioteca` (informado pelo `kindle-sys` real) for construído.
2. **Painel vira superfície de scope creep** (tentação de construir Chat/Documentos "de verdade" cedo demais). Mitigação: regra dura — conteúdo novo no painel só entra via campo do manifesto `Modulo`, nunca hardcoded na rota do Resumo Geral.
3. **Drift entre views SQL e funções Python equivalentes.** Mitigação: teste de paridade obrigatório no CI pras consultas legadas; consultas novas nascem view-first (sem duplicação possível).
4. **SQLite compartilhado com Metabase em container** (lock/leitura concorrente). Mitigação: Metabase é opcional e conecta read-only; o painel próprio não depende dele — se atritar, degrada pra deep-link/nada.
5. **Perda ou corrupção silenciosa do banco** (agora um registro financeiro real). Mitigação: backup diário automatizado + teste de restore mensal desde o v0.2.0; extratos brutos originais preservados como fonte de reimportação idempotente (via `fit_id`, herdado do v0.1).

## Verificação
- Cada v0.2.x: suíte completa verde (`pytest`), `ruff`+`mypy` limpos, critério "Utilizável" da tabela demonstrado com um comando real (não só testes passando).
- v0.2.0, adicional: saída de `saldo/gastos/categorias` idêntica à v0.1 sobre o mesmo banco (diff funcional zero); `git log --follow` funciona nos arquivos movidos (prova que os renames foram detectados).
- Verificação global de arquitetura: desligar API/painel/Metabase → CLI continua respondendo (prova que as camadas são de fato independentes); os números batem entre painel, API, CLI e views (uma única fonte de verdade).

## Execução
Processo: `subagent-driven-development` (implementador em **Sonnet** → spec review → quality review por tarefa, como no v0.1), em worktree novo (`personalos-v0.2`, a partir da `main` pós-merge). Cada fatia do roadmap (v0.2.0 … v0.2.4) ganha seu próprio plano de implementação detalhado via `writing-plans`, escrito e revisado antes de começar a implementar essa fatia especificamente — não escrevemos os 5 planos de uma vez.
