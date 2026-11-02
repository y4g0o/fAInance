🇺🇸 English · [🇧🇷 Português](README.pt-BR.md)

# fAInance

**Local, deterministic personal finance.** It reads your bank statements, learns your fixed expenses
on its own and answers decision questions — no data leaves your machine and no number comes from a
language model.

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](pyproject.toml)
[![Tests: pytest + vitest](https://img.shields.io/badge/tests-pytest%20%2B%20vitest-green.svg)](tests/)

![Batch categorization screen](docs/imagens/categorizar.png)

> The screen above solves the problem that kills personal finance tools: after importing a year of
> statements, everything starts uncategorized. Instead of asking for 200 clicks, the system groups the
> transactions, sorts the groups **by the money they represent** and learns a rule from each choice —
> half a dozen decisions cover most of the value.

The Python package and CLI are called **`personalos`** (PersonalOS): fAInance is its finance module,
built on a small modular kernel. UI text, CLI commands and code identifiers are in Portuguese.
Author: **Yago Macambira**.

## 💡 Why

A bank app shows what you spent. What nobody answers is what matters: *how much does it cost to exist
each month, where would cutting help most, and can I afford this in installments?* This project
answers those three, with numbers traceable to the function that produced them.

## ✨ Key features

- **Imports statements** in OFX, CSV, XLSX and **PDF**, reconciling against the balances declared in
  the document itself — if the sum does not match, the file is rejected instead of entering wrong.
- **Learns fixed expenses** from history: groups by normalized description, requires presence in
  ≥3 months and a stable amount. Zero LLM in the numbers.
- **Detects anomalies** with the modified z-score (median + MAD, Iglewicz-Hoaglin), because mean and
  standard deviation are contaminated precisely by the month you want to detect.
- **Answers decision questions**: basic cost of living, where to cut (ranked by annual impact), month-end
  projection, and the real interest hidden in an installment plan.
- **Local web interface** in React, with optimistic updates and undo.
- **Suggests a category from your own history** — only when there is a precedent, with the matching word
  shown. Without precedent it suggests nothing: an empty field beats a guess.
- **Simulates installment purchases** and shows the interest that "interest-free" hides.

## 🚀 Quickstart

Requirements: Python ≥ 3.12 and [uv](https://docs.astral.sh/uv/). Node.js only if you work on the web UI
(the built SPA is versioned in `src/personalos/web_dist/`).

```bash
git clone https://github.com/y4g0o/fAInance.git
cd fAInance
uv venv .venv && uv pip install --python .venv/bin/python -e .
.venv/bin/personalos servir        # web UI and API at http://127.0.0.1:8000/app/
```

Binding outside loopback is **refused with no escape hatch**: there is no authentication, and exposing it
would publish financial data on the network.

First steps with your own data:

```bash
cp ~/Downloads/statement.ofx extratos/            # extratos/ is git-ignored
.venv/bin/personalos financas importar             # imports every CSV/OFX/QFX/XLSX/PDF in extratos/
.venv/bin/personalos financas sugerir-regras       # where the uncategorized money is
.venv/bin/personalos financas custo-basico         # fixed costs + median of variable spending
```

Tests:

```bash
uv pip install --python .venv/bin/python -e ".[dev]"
.venv/bin/pytest          # back-end
cd web && npm ci && npm test        # pure front-end logic (vitest)
cd web && npm run e2e     # main flow in the browser (Playwright)
```

## 🧭 How it works

- **Modular kernel** (`src/personalos/nucleo/`) that **knows no module**, and modules in Clean Architecture
  (`dominio/` · `aplicacao/` · `infra/`). A test breaks the build if the web layer names a module — the
  boundary is mechanized, not agreed upon.
- The **CLI and the web interface call the same functions** in `aplicacao/`: a parity test
  (`tests/test_api_escrita.py`) fails the day an endpoint reimplements a business rule.
- **Every number comes from SQL or a pure function** ([ADR 0002](docs/adr/0002-llm-nunca-calcula.md)).
  The chat contract (`nucleo/portas/chat.py`) is built so that numbers and the tools that produced them
  are filled by code, never by an LLM.
- **SQLite** is the only database ([ADR 0001](docs/adr/0001-sqlite-como-banco-unico.md)), with WAL and
  write transactions opened with `BEGIN IMMEDIATE` (`nucleo/transacao.py`).

Layout:

- `src/personalos/nucleo/` — kernel: XDG config, shared engine (SQLite+WAL), write transaction
  (`BEGIN IMMEDIATE`), idempotent migrations, module contract (`Modulo`, a dataclass), memory
  (`nucleo_memoria`) and insights engine (`nucleo_insights`). **Imports no module** — see ADR 0006.
- `src/personalos/composicao.py` — composition root: the static list of plugged-in modules. It is the only
  layer that knows all of them.
- `src/personalos/modulos/<name>/` — each module is an independent package (Clean Architecture:
  dominio/aplicacao/infra + `cli.py` + `modulo.py` manifest). Tables are prefixed by module (`financas_*`)
  to avoid namespace collisions.
- `src/personalos/api/` — FastAPI app; `src/personalos/painel/` — the older Jinja panel;
  `web/` — the React + Vite + TypeScript SPA, built into `src/personalos/web_dist/`.
- `src/personalos/cli.py` — root CLI, aggregates the modules via `add_typer`.

### Decisions worth more than the code

The decisions that are expensive to reverse live in [`docs/adr/`](docs/adr/), each with context,
rationale and a **review trigger**. Start with the [index](docs/adr/README.md). Some of them:

| ADR | Decision |
|---|---|
| [0001](docs/adr/0001-sqlite-como-banco-unico.md) | SQLite as the only database |
| [0002](docs/adr/0002-llm-nunca-calcula.md) | **The LLM never calculates** — every number comes from SQL or a pure function |
| [0004](docs/adr/0004-convencao-de-sinal-nas-views.md) | A single sign convention in the views |
| [0006](docs/adr/0006-composition-root-fora-do-kernel.md) | Composition root outside the kernel |
| [0007](docs/adr/0007-painel-sem-javascript.md) | A panel without JavaScript — and why it was later replaced ([0008](docs/adr/0008-spa-react-substitui-painel-sem-js.md)) |
| [0010](docs/adr/0010-superficie-de-ataque-do-painel-local.md) | **Attack surface of a password-less local panel** — includes an exploitable flaw found and fixed |

### Triggers to revisit architecture decisions

- **Alembic** ← first destructive schema migration that the mini-engine in `nucleo/migracoes.py` handles poorly.
- **Postgres** ← a real need for a second concurrent writer process, or pgvector.
- **EventBus** ← the first real publisher/subscriber pair between two different modules.
- **YAML insight rules** ← when deterministic rules exceed ~10 (today: 3).
- **FastAPI API + panel** ← trigger fired and DELIVERED (v0.2.2 and v0.2.3): the chosen interface was a
  local web panel, so the API got a real consumer. The panel first shipped without HTMX or any JavaScript
  (ADR 0007), later replaced by the React SPA (ADR 0008).

## 📖 Usage in depth

<details>
<summary><strong>All CLI commands</strong></summary>

```bash
# finance module
.venv/bin/personalos financas regra uber Transporte
.venv/bin/personalos financas importar
.venv/bin/personalos financas saldo
.venv/bin/personalos financas gastos --mes 6 --ano 2026
.venv/bin/personalos financas categorias --mes 6
.venv/bin/personalos financas conta nubank "1.000,00"   # account opening balance
.venv/bin/personalos financas fluxo                      # inflow/outflow per month
.venv/bin/personalos financas lancar "cafe" 7,00         # manual entry (cash/PIX)
.venv/bin/personalos financas inspecionar-pdf extrato.pdf   # PDF layout, masked
.venv/bin/personalos financas sugerir-regras            # where the uncategorized money is
.venv/bin/personalos financas recategorizar            # applies rules to what is already stored

# decision questions (deterministic, no LLM)
.venv/bin/personalos financas custo-basico              # fixed + median of variable
.venv/bin/personalos financas onde-cortar --limite 5    # ranked by ANNUAL impact
.venv/bin/personalos financas pode-comprar 4500 --parcelas 10 --parcela 500
.venv/bin/personalos financas projecao                  # how the month should close

# learned fixed expenses and alerts
.venv/bin/personalos financas fixos                      # detects and lists fixed expenses
.venv/bin/personalos financas esquecer-fixo "deliveria pedido"  # removes a false positive
.venv/bin/personalos insights gerar
.venv/bin/personalos insights listar
.venv/bin/personalos insights dispensar 3                # will not come back
.venv/bin/personalos memoria listar --tipo gasto_fixo

# UI + API at http://127.0.0.1:8000 (loopback only)
.venv/bin/personalos servir

# backup
.venv/bin/personalos backup
```

</details>

<details>
<summary><strong>Web UI and API</strong></summary>

`personalos servir` runs the UI and the JSON API in the same process, on `127.0.0.1:8000`.
Binding outside loopback is **refused with no escape hatch**.

- `/app/` — the React SPA (import statements, fix balances, manual entries, batch categorization,
  analysis, purchase simulator). See [ADR 0008](docs/adr/0008-spa-react-substitui-painel-sem-js.md).
- `/` — the original Jinja panel, server-rendered SVG chart and plain HTML forms
  ([ADR 0007](docs/adr/0007-painel-sem-javascript.md)); it stays during the transition to the SPA.
- `/docs` — browsable API.

Neither UI knows any module by name: panel cards come from the `card` field of the module manifest, and
architecture tests fail the build if a module name appears in `painel/` or `web/src/shell/`.
Writes over HTTP require a loopback `Host` and a matching `Origin`
([ADR 0009](docs/adr/0009-escrita-http-e-verificacao-de-origem.md),
[ADR 0010](docs/adr/0010-superficie-de-ataque-do-painel-local.md)).

</details>

<details>
<summary><strong>Open without a terminal (systemd user service)</strong></summary>

```bash
./setup/instalar.sh
```

Installs a **user** service (never a system one, never root) that starts PersonalOS at login, and an
application-menu shortcut that opens `http://127.0.0.1:8000/app/`.

The service runs with the systemd sandbox: read-only disk, with writes allowed only in
`~/.local/share/personalos`, no privilege escalation. The bind stays locked to loopback by the program itself.

Diagnostics when something fails:

```bash
systemctl --user status personalos
journalctl --user -u personalos -n 50
```

Undo:

```bash
systemctl --user disable --now personalos
rm ~/.config/systemd/user/personalos.service ~/.local/share/applications/personalos.desktop
```

`personalos servir` keeps working in the terminal — it is the recovery path when the interface is broken.

</details>

<details>
<summary><strong>Categorizing without dying of boredom</strong></summary>

After importing a year of statements everything starts uncategorized — and without categories
`onde-cortar` only sees fixed expenses. `financas sugerir-regras` groups uncategorized transactions using
the same normalization as fixed-expense detection and sorts by the **amount** each group represents, not by
count: half a dozen rules cover most of the money.

The suggested pattern is the longest word common to every description in the group (between "PIX", "QRS"
and "TELECOMIX", the last one is what identifies it). Ties are broken alphabetically — `max()` over a set is
not deterministic, and a suggestion that changes between runs is worse than none. The reach column shows the
effect of the rule **before** creating it.

The category is always your choice; the tool only shows where the volume is.

</details>

<details>
<summary><strong>PDF statements</strong></summary>

`financas importar` accepts PDF, with two guards against silent failure — the typical failure mode of the
format: no line with a date and an amount may be skipped without classification, and the extracted sum is
reconciled against the balances declared in the statement itself, matched by date. If it does not close,
the file is rejected.

"Saldo do dia" (daily balance) lines are excluded: in the real statements tested they were ~30% of the
candidate lines, and importing them would create dozens of phantom transactions.

`financas inspecionar-pdf` shows the structure of a statement with everything **masked** (letter → `a`,
digit → `9`), to calibrate the reader for a new bank without exposing content. The output is safe to share;
the only residual leak is the number of digits, i.e. the order of magnitude of the amounts.

</details>

<details>
<summary><strong>Decision questions and method choices</strong></summary>

`custo-basico`, `onde-cortar`, `pode-comprar` and `projecao` are pure functions in `aplicacao/analise.py` —
they are the tools a conversational agent is meant to call. The LLM would choose which one to call and narrate;
no number comes from it.

Method choices, and why they matter:
- **Median, not mean**, in every monthly aggregate: an atypical month should not become your "normal".
- **Current month excluded** from medians: a half month would pull everything down.
- **`numpy-financial`** for installment money: `rate` recovers the interest embedded in "10x R$ 500" (that is
  how you find out that "interest-free" has 1.96%/month) and `pmt` computes the installment from a rate.
  Amortization and effective rate by hand are easy to get wrong.
- **The projection only accelerates variable spending** by the pace of days; fixed expenses do not multiply
  with the calendar, and what has not been charged yet enters as pending.
- **Anomaly by modified z-score** (median + MAD, cutoff 3.5 — Iglewicz-Hoaglin), falling back to a relative
  threshold when MAD is zero. Mean and standard deviation are contaminated by the very month you want to detect.
- `pode-comprar` **gives no verdict**: it returns installment, interest, slack and months of reserve.
  The decision is yours.

</details>

<details>
<summary><strong>Fixed expenses and insights</strong></summary>

`financas fixos` learns from history: it groups expenses by normalized description (without the digits
where the bank writes date and installment) and accepts as fixed what appears in ≥3 months, with a stable
amount (majority within ±25% of the median) and recent activity. The result is stored in `nucleo_memoria`,
so re-learning updates instead of duplicating, and your corrections survive.

None of this uses an LLM: every number comes from SQL/Python.

Current rules: a fixed expense that did not appear in the last month with activity (and that stops warning
when the absence is no longer recent, otherwise a cancelled subscription would nag forever); a fixed
expense that rose more than 10% over its median; a category out of the ordinary by the modified z-score.
A dismissed insight does not come back (dedup by `regra_id + chave_dedup`).

A recurring and roughly stable monthly expense (delivery, for example) may be classified as fixed — that
is the criterion working, not a bug. Use `esquecer-fixo` to remove it.

</details>

<details>
<summary><strong>Backup</strong></summary>

`personalos backup` creates a consistent copy of the database at
`~/.local/share/personalos/backups/personalos-<timestamp>.db` using SQLite's native backup API (safe even
while the database is in use).

There is no PersonalOS timer by design — call it from the scheduler you already have. In the author's
setup, a nightly script runs `personalos backup` before restic, so the consistent snapshot goes into the
system backup (restic alone would copy the file in use, which is not safe with WAL); it keeps the 7 most
recent local snapshots and restic holds the long history.

Restore = copy the backup file back to the database path (`~/.local/share/personalos/personalos.db`).
The original raw statements in `extratos/` are the source for idempotent re-import (dedup by `fit_id`) —
keep them as additional disaster recovery.

</details>

<details>
<summary><strong>Dashboard with Metabase (optional)</strong></summary>

Metabase is an optional visualization tool — PersonalOS does not need it. It reads the views
(`vw_financas_*_v1`) of the real database, read-only.

```bash
docker compose --profile metabase up -d
```

Then open `http://localhost:3000` (bound to loopback only), complete the initial setup, and add a database
connection pointing to the file mounted at `/data/personalos.db` (type SQLite). This is done once, in the
UI — not automated by design (personal tool, one-time use).

</details>

## 📌 Project status & limitations

- Version **0.2.4**, single-user, maintained by one person; Linux is the only setup with an installer
  (`setup/` uses systemd user units).
- **No authentication by design**: it only binds to loopback. Read
  [ADR 0010](docs/adr/0010-superficie-de-ataque-do-painel-local.md) before changing anything network-related.
- **Conversational chat is not shipped**: the contract (`nucleo/portas/chat.py`) and `POST /api/chat` exist,
  but `personalos servir` starts without a chat service, so the endpoint answers `501 Not Implemented`.
- Bank coverage is limited to what was tested: CSV header mappings live in
  `modulos/financas/infra/leitores/csv_.py`; PDF layouts vary per bank, and a new bank should be calibrated
  first with `inspecionar-pdf`.
- A recurring, stable variable expense (e.g. delivery) may be detected as fixed — use `esquecer-fixo`.
- Two UIs coexist during the transition (`/` Jinja, `/app/` SPA), and `node_modules` is the one part of
  the system that needs continuous maintenance (accepted cost, ADR 0008).

## 🗺️ Roadmap

1. **Retire the Jinja panel** and serve the SPA at the root, as planned in ADR 0008 (the SPA uses
   `base: '/app/'` only while the panel occupies `/`).
2. **Conversational consultant** implementing `ServicoChat` over the local Ollama HTTP API, calling the
   deterministic functions in `aplicacao/analise.py` — no agent framework (ADR 0002, ADR 0003).
3. **More bank layouts**: new CSV mappings and PDF calibration via `inspecionar-pdf`.
4. **More deterministic insight rules** (3 today); move them to YAML once they pass ~10, per the trigger above.
5. **Adopt `ruff format`** across the code base (`ruff check` already passes; formatting is not yet applied
   to most files).

## 🤝 Contributing

Issues and PRs are welcome — tests, bank formats, docs and UI polish especially.
See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, conventions and a list of good first issues.

## 📄 License

MIT — see [`LICENSE`](LICENSE).
