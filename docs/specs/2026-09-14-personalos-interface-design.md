# PersonalOS — Interface própria (SPA React)

> Aprovado em 2026-09-14. Substitui a interface do v0.2.3 (painel Jinja sem
> JavaScript) e aposenta o ADR 0007.

---

## Contexto

O PersonalOS chegou ao fim do roadmap v0.2.x com tudo funcionando e quase nada
usável no dia a dia. O painel entregue no v0.2.3 tem 73 linhas de template, um
gráfico de barras e uma caixa de pergunta que sempre devolve erro. A CLI tem 20
comandos que ninguém decora.

O estado do banco explica a urgência: algumas centenas de transações
importadas e **a maioria sem categoria**, com o saldo inicial da conta ainda num
valor de teste que nunca foi corrigido. As ferramentas de decisão
(`onde-cortar`, `custo-basico`, `projecao`) funcionam, mas respondem sobre
categorias de banco (`Conta de uso`, `Cartão`) em vez de categorias de gasto —
ou seja, funcionam e não servem.

O pedido do usuário: *"uma interface bonita e intuitiva para utilizar e
atualizar meus dados, fazer minhas perguntas e ver meus gastos"*.

## Decisões tomadas no brainstorming

| Decisão | Escolha | Consequência |
|---|---|---|
| Onde usa | PC de casa, `127.0.0.1` | Sem autenticação, sem exposição de rede. Celular fica pra depois e o design não fecha essa porta |
| Ordem | Dados → dashboards → consultor | Cada etapa utilizável sozinha; dashboard só faz sentido sobre dados categorizados |
| Stack | **React + Vite + TypeScript** | Escolhido pelo tamanho do material de treino (assistência de IA acerta mais) e ecossistema. Custo aceito: npm e `node_modules` |
| Fronteira | Moldura genérica + telas sob medida | O ADR 0006 sobrevive onde importa; as telas de finanças podem ser boas |
| Extrato do banco | Só a categoria é editável | Banco continua fonte da verdade; reimportação nunca briga com edição |
| Categorizar | **Por grupo, ensinando regra** | ~10 decisões resolvem 174 transações e o sistema aprende pro futuro |
| Visual | **Escuro e denso**, tema claro alternável | Cor como sinal; ano inteiro visível sem rolar |
| Interação | **Detalhes reativos** | Sem reload; atualização otimista com rollback |

## Princípio: a aplicação basta

Requisito do usuário, em 14/09/2026: **"o usuário deve conseguir fazer tudo pela
própria aplicação"**. Nenhuma tarefa rotineira pode exigir terminal.

Isso é mais forte do que "ter uma interface bonita" e muda duas coisas:

1. **Paridade é critério de aceite**, não consequência. Cada comando da CLI tem
   um destino declarado na tabela abaixo — tela, ou fora de escopo com motivo.
2. **A aplicação precisa subir sem terminal.** `personalos servir` é o comando
   que *liga* o sistema: ele não pode viver dentro do sistema. Sem resolver
   isso, o princípio quebra no passo zero — o usuário abriria o terminal
   justamente para não precisar dele. Entra no P1: serviço systemd de usuário
   que sobe no login e um atalho no menu de aplicativos que abre o navegador na
   página. A partir daí o PersonalOS se comporta como um aplicativo instalado.

A CLI **continua existindo e mantida** — paridade não é remoção. Ela é o que a
rotina noturna chama (`personalos backup`), é scriptável, e é o caminho de
recuperação quando a interface estiver quebrada.

### Inventário: os 25 comandos e onde cada um aparece

| Comando | Vira o quê na interface | Quando |
|---|---|---|
| `financas importar` | Arrastar arquivo na tela | **P1** |
| `financas lancar` | Formulário de lançamento manual | **P1** |
| `financas regra` | Criado junto na tela de categorizar | **P1** |
| `financas recategorizar` | Botão "reaplicar regras" | **P1** |
| `financas conta` | Edição do saldo inicial | **P1** |
| `financas sugerir-regras` | É a própria tela de categorizar | **P1** |
| `financas saldo` | Cartão no Resumo (já existe) | **P1** |
| `insights listar` / `dispensar` | Lista de alertas com botão (já existe) | **P1** |
| `financas gastos` | Tela de gastos do período | P2 |
| `financas categorias` | Gráfico de gasto por categoria | P2 |
| `financas fluxo` | Gráfico de fluxo mensal (já existe, melhora) | P2 |
| `financas custo-basico` | Cartão no Resumo | P2 |
| `financas onde-cortar` | Tela de candidatos a corte | P2 |
| `financas projecao` | Cartão "como o mês deve fechar" | P2 |
| `financas pode-comprar` | Simulador com campos de valor e parcelas | P2 |
| `financas fixos` | Lista de gastos fixos aprendidos | P2 |
| `financas esquecer-fixo` | Botão de remover na lista de fixos | P2 |
| `memoria listar` / `esquecer` | Tela do que o sistema aprendeu | P2 |
| `insights gerar` | Botão "procurar alertas agora" | P2 |
| `backup` | Botão + aviso de quando foi o último | P2 |
| `servir` | **Vira serviço no login + atalho no menu** | **P1** |
| `financas inspecionar-pdf` | **Fora de escopo, com motivo:** é diagnóstico para calibrar o leitor de um banco novo, usado durante desenvolvimento. Segue só na CLI | — |

## Decomposição

Três projetos, cada um com spec e plano próprios. **Esta spec detalha o P1**;
P2 e P3 aparecem só como contexto e podem mudar.

| | Projeto | Entrega | Utilizável = |
|---|---|---|---|
| **P1** | Escrita + SPA base | API de escrita, esqueleto da SPA, fluxo de categorização em lote, correção de saldo, lançamento manual, upload de extrato, **arranque sem terminal** | As transações órfãs categorizadas pela tela, saldo correto, extrato novo entrando sem terminal, e o PersonalOS abrindo por um ícone |
| **P2** | Dashboards | Telas de análise sobre dados já categorizados | Abrir e entender pra onde foi o dinheiro sem rodar comando |
| **P3** | Consultor | Implementar `ServicoChat` — LLM local escolhendo entre as funções determinísticas existentes | Perguntar "posso comprar isso?" e receber resposta com os números citados |

---

## P1 — Arquitetura

### Layout físico

```
personalos/
  web/                          projeto Vite (package.json, src/, node_modules/)
    src/
      shell/                    moldura: layout, navegação, tema — NÃO conhece módulo
      modulos/financas/         telas específicas de finanças
      lib/                      cliente da API, formatação de dinheiro, hooks
  src/personalos/web_dist/      build gerado, versionado no git
  src/personalos/painel/        Jinja atual — mantido até o fim do P2
```

### A fronteira que substitui o teste do ADR 0006

Hoje um teste de arquitetura falha o build se o nome de um módulo aparecer em
`painel/`. A regra continua, com escopo novo:

- **`web/src/shell/`** não pode conter o nome de nenhum módulo. Descobre as
  seções pela API (`/api/saude` já devolve a lista de módulos ativos) e monta a
  navegação a partir dela. Teste automatizado equivalente ao atual.
- **`web/src/modulos/<nome>/`** conhece o próprio domínio à vontade.

Quando entrar o segundo módulo, ele ganha uma pasta e o shell não muda.

### Build e entrega

`npm run build` gera estático que o FastAPI serve — **um processo só**, nada de
servidor de front separado em uso normal. O dev server do Vite existe apenas
durante desenvolvimento, com proxy para a API. Em uso normal quem dispara
`servir` é o serviço de usuário, não o usuário (ver "Princípio: a aplicação
basta").

**`web_dist/` é versionado no git.** O diff fica sujo a cada build, e aceitamos:
o usuário é o único instalador, e ficar sem interface porque o Node não está
instalado é pior que um diff feio. Consequência prática: o build entra no commit
junto com a mudança que o gerou, nunca sozinho.

---

## P1 — Superfície de escrita da API

Hoje a API tem 9 endpoints, **todos GET**. Toda escrita vive só na CLI.

| Endpoint | Ação |
|---|---|
| `PUT /api/financas/contas/{nome}` | Saldo inicial da conta |
| `POST /api/financas/lancamentos` | Lançamento manual (dinheiro, PIX fora do extrato) |
| `PATCH /api/financas/transacoes/{id}` | Categoria de uma transação (só categoria) |
| `POST /api/financas/transacoes/categorizar-em-lote` | Categoria para um grupo, opcionalmente criando regra |
| `POST /api/financas/regras` | Nova regra padrão → categoria |
| `POST /api/financas/recategorizar` | Reaplica regras ao que já está gravado |
| `POST /api/financas/extratos` | Upload de extrato (OFX/CSV/PDF) |
| `PATCH /api/insights/{id}/status` | Já existe |

**Regra inegociável:** nenhum endpoint reimplementa lógica. Cada um chama a
mesma função de `aplicacao/` que o comando de CLI correspondente chama. As
defesas moram lá (valor como magnitude + sinal vindo do tipo; validação de
número vindo de LLM; dedup por `fit_id`), e duplicá-las garantiria divergência
futura.

**Consequência aceita:** o upload de extrato exige `python-multipart`, que o
ADR 0007 tinha evitado deliberadamente. Justificativa: lá era para não instalar
uma dependência por causa de um formulário de um campo; aqui é upload de
arquivo binário, que é exatamente o caso de uso dela.

---

## P1 — Segurança

O painel atual é seguro por ser só leitura em loopback. Com escrita, aparece
CSRF: qualquer site aberto no mesmo navegador pode disparar POST para
`127.0.0.1:8000`. Não lê a resposta, mas grava.

**Proteção nesta fase:** o servidor recusa toda requisição de escrita cujo
cabeçalho `Origin` não seja o próprio painel. O navegador não deixa um site
forjar `Origin`, então isso fecha o vetor. Sem senha, sem login — o usuário
continua abrindo `localhost:8000` e usando.

**Pendência explícita:** o usuário pediu uma **revisão de segurança do sistema
inteiro** depois desta etapa. Escopo mínimo dessa revisão: bind e recusa de
não-loopback, upload de arquivo (tamanho, tipo, path traversal), SQL via
SQLAlchemy, o que o backup expõe em disco, e o que o Metabase enxerga.

---

## P1 — O fluxo de categorização

A tela que resolve as transações órfãs. Reusa `sugerir-regras`, que já existe
e já ordena os grupos **por dinheiro**, não por contagem.

**Como funciona:**
1. A tela lista os grupos detectados, do maior valor pro menor, com quantas
   transações cada um tem e quanto dinheiro representa.
2. O usuário escolhe uma categoria por grupo. Categoria existente ou nova, ali
   mesmo, sem sair da tela.
3. Um checkbox por grupo — **ligado por padrão** — cria também a regra, para os
   próximos extratos nascerem categorizados.
4. "Aplicar" grava tudo de uma vez.

**O que os números do banco mostraram** ao desenhar a tela: só uma fração das
transações sem categoria são despesas — o resto é receita e movimentação entre
contas. E os 6 maiores grupos sugeridos cobriam pouco mais de **metade** do valor
das despesas órfãs. Isso mata metade do problema com 6 decisões,
mas não "quase tudo": a cauda é grande e a tela precisa mostrar o progresso
(quanto do seu dinheiro já tem categoria) para a tarefa ter fim visível.

**A cauda:** sobram avulsos sem grupo. O P1 entrega uma lista simples para eles;
a fila item-a-item (opção B do brainstorming, boa para manutenção mensal) fica
fora do escopo e entra se a dor aparecer.

**Risco conhecido:** regra ampla demais pega o que não devia (`brasil` pegaria
qualquer descrição com "brasil"). Mitigação: a tela mostra o alcance da regra
**antes** de aplicar — quantas transações existentes ela pegaria — que é
informação que `sugerir-regras` já calcula.

---

## P1 — Direção visual

**Escuro por padrão, denso, com tema claro alternável.** O alternador nasce
junto: é barato de origem e caro de enxertar depois.

- **Cor é sinal, não decoração.** Verde entra, vermelho sai, neutro é o resto.
  Nada de cor por enfeite — quando tudo é colorido, nada chama atenção.
- **Densidade alta:** o ano inteiro de fluxo cabe sem rolagem.
- **Números tabulares** (`font-variant-numeric: tabular-nums`) em toda coluna de
  dinheiro, para os dígitos alinharem e a comparação ser visual.
- **Contraste conferido** contra WCAG AA. Tema escuro erra fácil nisso.

## P1 — Detalhes reativos

Requisito explícito do usuário. Concretamente:

- **Atualização otimista:** escolher a categoria de um grupo atualiza a linha e
  recalcula os totais na hora, sem esperar o servidor. Se o servidor recusar, a
  interface **desfaz visivelmente** e diz por quê — o caminho de rollback é
  parte da entrega, não detalhe de implementação.
- **Desfazer** por alguns segundos depois de aplicar em lote. Aplicar categoria
  errada a 11 transações precisa ter volta.
- **Estados de carregamento** com esqueleto da tela, nunca tela branca.
- **Hover e foco sempre visíveis**, incluindo navegação por teclado.
- **Gráfico responde ao mouse:** valor e mês do que está sob o cursor.
- **Transições curtas** (~150 ms) em mudança de estado, respeitando
  `prefers-reduced-motion`.
- **Nenhum reload de página** em operação normal.

---

## P1 — Testes

| Camada | Ferramenta | O que cobre |
|---|---|---|
| API de escrita | pytest (os 249 atuais continuam verdes) | Cada endpoint; paridade com a CLI — mesma operação pelos dois caminhos produz o mesmo estado |
| Segurança | pytest | Escrita com `Origin` errado é recusada; bind não-loopback é recusado |
| Arquitetura | pytest | O shell não menciona módulo nenhum |
| Lógica pura do front | Vitest | Formatação de dinheiro, agrupamento, cálculo otimista e rollback |
| Fluxo de ponta a ponta | Playwright | Categorizar um grupo pela tela e conferir que o banco mudou |

**Não** vamos montar pirâmide de teste de componente React. É ferramenta
pessoal: teste onde erro custa dinheiro (as contas) ou trava o uso (o fluxo
principal).

## Decisões de arquitetura a registrar

- **ADR 0008 — SPA React substitui painel sem JavaScript.** Marca a 0007 como
  substituída, com o motivo honesto: a decisão de zero JS estava certa para um
  painel de leitura com um gráfico, e deixou de estar quando a interface virou o
  jeito principal de usar o sistema. Deve registrar o custo aceito (npm como
  única parte do sistema que exige manutenção contínua) e o gatilho de
  arrependimento: se em um ano o `npm install` estiver quebrando sozinho, voltar
  para HTML servido.
- **ADR 0009 — Escrita via HTTP e verificação de origem.**

## Decisões fechadas em 14/09/2026 (pós-investigação do repositório)

A investigação do código levantou duas decisões que a spec não tinha previsto.
Ambas aprovadas pelo usuário:

**A — Contrato da categorização em lote.** O cliente manda o **padrão** e o
servidor recalcula o grupo; o agrupamento nunca sai de `aplicacao/sugestoes.py`
para o React. A resposta devolve a **lista de `fit_id` efetivamente alterados**,
que é o que o desfazer precisa para voltar exatamente o que mudou — nem mais,
nem menos.

**B — Onde o upload grava o extrato.** Em `~/.local/share/personalos/extratos/`
(XDG, ao lado do banco), não na pasta `extratos/` do checkout. Motivos: extrato
bancário não entra na árvore de trabalho do git nem por acidente; funciona com o
pacote instalado, enquanto `EXTRATOS_PADRAO` hoje é derivado de
`__file__.parents[4]`; e o backup passa a cobrir banco e extratos no mesmo lugar.
A pasta antiga continua aceita como argumento explícito de `financas importar`.

### Divergências do código que o P1 precisa corrigir

Encontradas na investigação, todas registradas para não virarem surpresa:

1. **`lancar`, `regra` e `conta` têm regra de negócio dentro de `cli.py`** — não
   existe função em `aplicacao/` para a API chamar. Extrair isso é a Fase 1, e é
   pré-requisito da regra "nenhum endpoint duplica lógica".
2. **Não existe `id` inteiro em transação.** A PK é `fit_id` (String), então o
   endpoint é `PATCH /api/financas/transacoes/{fit_id}`.
3. **Nenhum repositório atualiza a categoria de uma transação** — só o `UPDATE`
   inline dentro de `recategorizar`.
4. **`/api/saude` responde `0.2.1`**, literal em `api/app.py`, enquanto o
   pyproject está em 0.2.4.
5. **O teste de arquitetura de `api/` proíbe a string `personalos.modulos`**, então
   o upload precisa morar no router do módulo, não em `api/app.py`.
6. **`SugestaoRegra` não devolve os `fit_id` do grupo** — daí a decisão A.
7. **`lancar` usa a conta `manual` com aviso de dupla contagem**; a tela precisa
   carregar esse aviso, senão a interface vira máquina de duplicar gasto.


## Princípio: abstenção vence invenção

Declarado pelo usuário em 14/09/2026: **"não sei" é melhor do que a invenção**.

O PersonalOS é determinístico. Todo número que a interface mostra vem de SQL ou
de função pura em `aplicacao/` — nunca de modelo de linguagem. Isso já está no
ADR 0002; o que se acrescenta aqui é a consequência para o P3 e para a interface:

- **O consultor (P3) não é fonte de informação, é roteador.** Ele escolhe qual
  função determinística chamar e narra o resultado. Quando não existe função que
  responda à pergunta, a resposta correta é dizer que não sabe — não estimar,
  não arredondar de cabeça, não preencher lacuna com plausibilidade. O contrato
  em `nucleo/portas/chat.py` já prevê isso com `degradado` e `motivo`.
- **Na interface (P1 e P2), dado ausente se mostra como ausente.** Nada de zero
  no lugar de "sem dado", nada de linha de exemplo em estado vazio, nada de
  projeção apresentada com a mesma tipografia de um valor medido. O painel atual
  já acerta nisso ("Nenhum movimento no mês corrente — nada a projetar"), e a SPA
  precisa herdar o mesmo rigor.
- **Todo número exibido deve ser rastreável** até a função que o produziu — é
  para isso que o contrato de chat carrega `numeros` e `ferramentas`.

Em sistema financeiro pessoal, o erro por invenção é pior que o erro por
omissão: a omissão você percebe e vai atrás; a invenção você acredita.


### P3 — o que o usuário espera do consultor (registrado em 14/09/2026)

Pedido: ver padrões de gasto e de perfil, sugerir economia, fazer perguntas de
volta, e dizer **quando dá para gastar em determinado mês** — com a expectativa,
correta, de que isso melhore ano a ano.

A divisão que o P3 precisa respeitar:

- **Detecção é determinística e em boa parte já existe:** `fixos` (assinaturas
  aprendidas), insight por z-score modificado (anomalia), `onde-cortar`,
  `custo-basico`, `projecao`, `pode-comprar`.
- **Falta de verdade: sazonalidade.** Nenhuma análise atual compara mês do ano
  com o mesmo mês de outros anos — tudo compara com a mediana geral. "Quando dá
  para gastar em março" exige isso, e é função nova em `aplicacao/analise.py`,
  não trabalho de modelo.
- **O Agno entra como roteador e narrador:** escolhe qual função responde,
  ordena o que importa agora, narra em português e devolve pergunta quando a
  frase é ambígua. Nunca calcula. Ver "abstenção vence invenção".
- **RAG fica fora de finanças.** Recuperar texto para responder sobre número é
  o caminho por onde a invenção entra. Cabe no módulo 2 (e-mail), onde o
  conteúdo é texto de verdade.
- **Quando o P3 começar, escrever ADR substituindo o 0003** ("sem framework de
  agente nem RAG"): o gatilho dele era não haver consumidor real, e agora há.

**Limite que modelo nenhum resolve:** previsão é limitada pela cobertura do
dado. Com poucos meses de histórico e uma conta só, não há base para afirmação
sazonal nenhuma. Importar o que falta vale mais que qualquer escolha de modelo, e
cada mês sem dado é um mês que não poderá ser comparado depois.


## Fora de escopo

Celular e acesso remoto; autenticação; a fila de categorização item-a-item;
dashboards (P2); consultor conversacional (P3); aposentar o painel Jinja (fim do P2).

**O bot do Telegram foi abandonado** (decisão do usuário, 14/09/2026). Ele já
estava desplugado de `agentes/telegram_bot.py`, e não será religado: a interface
web passa a ser o único caminho, coerente com "o usuário deve conseguir fazer
tudo pela própria aplicação". Consequência: `agentes/financas.py` e
`agentes/financas_nl.py` viram código morto — ficam onde estão até o usuário
decidir removê-los, mas não recebem manutenção.

O benchmark de modelos locais continua valendo para o P3 (o consultor roda na
tela, não no Telegram), só perdeu a urgência: não há mais um caminho em produção
errando hoje.

## Critérios de sucesso do P1

1. As transações sem categoria são resolvidas **pela tela**, em poucos minutos,
   sem abrir terminal.
2. O saldo exibido bate com o do banco, com o valor de teste corrigido pela
   própria interface.
3. Um extrato novo entra arrastando o arquivo na tela.
4. **O PersonalOS abre sem terminal** — serviço sobe no login, ícone no menu abre
   a página. Nenhuma tarefa do P1 exige linha de comando.
5. Os 249 testes continuam verdes, mais os novos de escrita, segurança e o
   Playwright do fluxo principal.
6. Nenhuma operação normal recarrega a página.

## Riscos

- **Retrabalho visual.** Direção escolhida a partir de mockup estático; a
  sensação real só aparece com dados na tela. Mitigação: a densidade é o que
  guia, e o alternador de tema nasce junto.
- **`node_modules` envelhecendo.** É o custo assumido da decisão. O gatilho de
  arrependimento está no ADR 0008.
- **Otimismo sem rollback** é a falha clássica desse tipo de interface: a tela
  mostra sucesso e o banco não mudou. Por isso o rollback é critério de entrega,
  não polimento.
