# Contributing · Como contribuir

🇺🇸 [English](#english) · 🇧🇷 [Português](#português)

---

## English

Thanks for your interest! fAInance handles real financial data, so two rules come before everything else:

- **No number may come from an LLM** — every number comes from SQL or a tested pure function
  ([ADR 0002](docs/adr/0002-llm-nunca-calcula.md)).
- **Never commit real statements or databases.** Use the synthetic fixtures in `tests/fixtures/` and
  `tests/pdf_sintetico.py`; `extratos/` is git-ignored on purpose.

### Setup

```bash
git clone https://github.com/y4g0o/fAInance.git
cd fAInance
uv venv .venv && uv pip install --python .venv/bin/python -e ".[dev]"   # Python >= 3.12
```

Use `.venv/` at the repository root: `setup/instalar.sh` and the e2e server script (`web/e2e/servidor.sh`)
expect it there.

For the web UI (Node.js):

```bash
cd web
npm ci
npm run dev        # Vite dev server; proxies /api to http://127.0.0.1:8000 (run `personalos servir` too)
npm run build      # type-checks and writes the SPA into src/personalos/web_dist/ (versioned)
```

### Running tests

```bash
.venv/bin/pytest             # back-end (pytest); offline, a few seconds
cd web && npm test           # front-end pure logic (vitest)
cd web && npm run e2e        # browser flow (Playwright) on a throwaway seeded database
```

The e2e run starts its own server on port 8020 against a disposable database — no test touches your real
data. You may need to install the Playwright browsers once (`npx playwright install`).

### Code style

- **Python:** `ruff` (`line-length = 100`, `target-version = "py312"`) and `mypy` with
  `disallow_untyped_defs = true`, both configured in `pyproject.toml`:

  ```bash
  .venv/bin/ruff check src tests
  .venv/bin/mypy
  ```

  `ruff format` has **not** been applied to the code base yet — don't reformat files you are not otherwise
  changing; a code-wide format is its own PR.
- **TypeScript/React:** `npm run lint` (oxlint, `web/.oxlintrc.json`) and `tsc` via `npm run build`.
- Identifiers, comments, docstrings and UI text are in **Portuguese**, like the rest of the code.
- Docstrings explain *why*. A decision that is expensive to reverse gets an ADR in `docs/adr/` — see
  [when to open one](docs/adr/README.md).
- Respect the boundaries that tests enforce: `nucleo/`, `painel/` and `web/src/shell/` must not name any
  module; CLI and API must call the same `aplicacao/` functions. Money travels as integer cents.
- Anything touching HTTP, binding or file permissions: read
  [ADR 0009](docs/adr/0009-escrita-http-e-verificacao-de-origem.md) and
  [ADR 0010](docs/adr/0010-superficie-de-ataque-do-painel-local.md) first.

### Branch / PR flow

1. Fork and create a branch from `main`: `fix/<short-name>`, `test/<short-name>`, `docs/<short-name>` or
   `feat/<short-name>`.
2. Keep PRs small — one issue per PR. Rebuild `src/personalos/web_dist/` (`npm run build`) only when the PR
   changes `web/src/`.
3. Before pushing: `pytest`, `ruff check`, `mypy`, and for web changes `npm test` and `npm run lint`.
4. In the PR description, say what changed, why, and how you verified it.

### Good first issues

1. **Fix the web lint error.** `npm run lint` currently fails with two `react-hooks(rules-of-hooks)`
   errors in `web/src/shell/Shell.tsx`: the hook `usarTema` does not start with `use`. Rename it
   (e.g. `useTema`) and update its call site.
2. **Make `test_arquivo_sem_permissao_gera_erro_claro` robust when running as root.** In
   `tests/test_leitor_csv.py` the test `chmod 000`s a file and expects an error, but root (containers, CI
   runners, user namespaces) can still read it, so the test fails there. Skip it when `os.geteuid() == 0`.
3. **Update the stale docstring of `infra/leitores/pdf.py`.** Its "Estado atual" paragraph says the reader
   and the two guards are not implemented yet, but `LeitorPDF.ler` and `LeitorPDF.reconciliar` exist and are
   covered by `tests/test_leitor_pdf.py`. Rewrite that paragraph to match the code.
4. **Replace the Vite boilerplate in `web/README.md`.** It is the untouched "React + TypeScript + Vite"
   template. Replace it with what a front-end contributor needs: `npm run dev` with the `/api` proxy,
   `npm run build` output to `src/personalos/web_dist/`, the `base: '/app/'` reason, tests and lint.
5. **Unit-test `nucleo/transacao.py`.** `escrita()` (`BEGIN IMMEDIATE`, commit, rollback on exception) is
   only exercised indirectly through migrations and repositories. Add `tests/test_nucleo_transacao.py`
   covering: commit on success; rollback when the block raises (row not persisted, exception re-raised).
6. **Unit-test `web/src/lib/api.ts`.** It is the only file in `web/src/lib/` without a `.test.ts`. With a
   stubbed `fetch` (`vi.stubGlobal`), cover: JSON on success; `ErroDaApi` carrying `status` and the `detail`
   from the body; the fallback message `Falhou (<status>)` when the error body is not JSON.

---

## Português

Obrigado pelo interesse! O fAInance lida com dados financeiros reais, então duas regras vêm antes de tudo:

- **Nenhum número pode vir de LLM** — todo número vem de SQL ou de função pura testada
  ([ADR 0002](docs/adr/0002-llm-nunca-calcula.md)).
- **Nunca versione extratos ou bancos reais.** Use as fixtures sintéticas de `tests/fixtures/` e
  `tests/pdf_sintetico.py`; `extratos/` é ignorada pelo git de propósito.

### Configuração

```bash
git clone https://github.com/y4g0o/fAInance.git
cd fAInance
uv venv .venv && uv pip install --python .venv/bin/python -e ".[dev]"   # Python >= 3.12
```

Use `.venv/` na raiz do repositório: o `setup/instalar.sh` e o script do servidor do e2e
(`web/e2e/servidor.sh`) esperam o ambiente ali.

Para a interface web (Node.js):

```bash
cd web
npm ci
npm run dev        # dev server do Vite; manda /api para http://127.0.0.1:8000 (rode `personalos servir` junto)
npm run build      # checa tipos e grava a SPA em src/personalos/web_dist/ (versionado)
```

### Rodando os testes

```bash
.venv/bin/pytest             # back-end (pytest); offline, alguns segundos
cd web && npm test           # lógica pura do front (vitest)
cd web && npm run e2e        # fluxo no navegador (Playwright) num banco descartável semeado
```

O e2e sobe o próprio servidor na porta 8020 com um banco descartável — nenhum teste toca os seus dados reais.
Pode ser preciso instalar os navegadores do Playwright uma vez (`npx playwright install`).

### Estilo de código

- **Python:** `ruff` (`line-length = 100`, `target-version = "py312"`) e `mypy` com
  `disallow_untyped_defs = true`, ambos configurados no `pyproject.toml`:

  ```bash
  .venv/bin/ruff check src tests
  .venv/bin/mypy
  ```

  O `ruff format` **ainda não** foi aplicado ao código — não reformate arquivos que você não está mudando
  por outro motivo; formatar o código todo é um PR à parte.
- **TypeScript/React:** `npm run lint` (oxlint, `web/.oxlintrc.json`) e `tsc` via `npm run build`.
- Identificadores, comentários, docstrings e textos da interface em **português**, como no resto do código.
- Docstrings explicam o *porquê*. Decisão cara de reverter ganha um ADR em `docs/adr/` — veja
  [quando abrir um](docs/adr/README.md).
- Respeite as fronteiras que os testes garantem: `nucleo/`, `painel/` e `web/src/shell/` não podem citar
  módulo nenhum; CLI e API chamam as mesmas funções de `aplicacao/`. Dinheiro trafega em centavos inteiros.
- Qualquer mudança em HTTP, bind ou permissão de arquivo: leia antes o
  [ADR 0009](docs/adr/0009-escrita-http-e-verificacao-de-origem.md) e o
  [ADR 0010](docs/adr/0010-superficie-de-ataque-do-painel-local.md).

### Fluxo de branch / PR

1. Faça um fork e crie uma branch a partir de `main`: `fix/<nome-curto>`, `test/<nome-curto>`,
   `docs/<nome-curto>` ou `feat/<nome-curto>`.
2. PRs pequenos — uma tarefa por PR. Recompile `src/personalos/web_dist/` (`npm run build`) só quando o PR
   mudar `web/src/`.
3. Antes do push: `pytest`, `ruff check`, `mypy` e, para mudanças no web, `npm test` e `npm run lint`.
4. Na descrição do PR, diga o que mudou, por quê e como você verificou.

### Boas primeiras tarefas

1. **Corrigir o erro de lint do web.** `npm run lint` falha hoje com dois erros `react-hooks(rules-of-hooks)`
   em `web/src/shell/Shell.tsx`: o hook `usarTema` não começa com `use`. Renomeie (ex.: `useTema`) e
   atualize onde ele é chamado.
2. **Deixar `test_arquivo_sem_permissao_gera_erro_claro` robusto rodando como root.** Em
   `tests/test_leitor_csv.py` o teste faz `chmod 000` num arquivo e espera erro, mas o root (containers,
   runners de CI, user namespaces) ainda consegue ler, e o teste falha. Pule-o quando `os.geteuid() == 0`.
3. **Atualizar a docstring desatualizada de `infra/leitores/pdf.py`.** O parágrafo "Estado atual" diz que o
   leitor e as duas guardas ainda não existem, mas `LeitorPDF.ler` e `LeitorPDF.reconciliar` existem e são
   cobertos por `tests/test_leitor_pdf.py`. Reescreva o parágrafo de acordo com o código.
4. **Trocar o boilerplate do Vite em `web/README.md`.** É o template "React + TypeScript + Vite" intocado.
   Substitua pelo que quem mexe no front precisa: `npm run dev` com o proxy de `/api`, saída do
   `npm run build` em `src/personalos/web_dist/`, o motivo do `base: '/app/'`, testes e lint.
5. **Testar `nucleo/transacao.py` diretamente.** `escrita()` (`BEGIN IMMEDIATE`, commit, rollback em
   exceção) só é exercitada indiretamente por migrações e repositórios. Crie `tests/test_nucleo_transacao.py`
   cobrindo: commit no sucesso; rollback quando o bloco levanta (linha não persiste, exceção propagada).
6. **Testar `web/src/lib/api.ts`.** É o único arquivo de `web/src/lib/` sem `.test.ts`. Com `fetch` simulado
   (`vi.stubGlobal`), cubra: JSON no sucesso; `ErroDaApi` com `status` e o `detail` do corpo; a mensagem
   padrão `Falhou (<status>)` quando o corpo do erro não é JSON.
