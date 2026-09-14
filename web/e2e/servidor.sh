#!/usr/bin/env bash
# Sobe o PersonalOS num banco descartável, semeado, para o teste de ponta a ponta.
# Banco próprio de propósito: teste que escreve no banco real é teste que um dia
# apaga o mês do usuário.
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BANCO="${PERSONALOS_E2E_DB:-/tmp/personalos-e2e.db}"
PORTA="${PERSONALOS_E2E_PORTA:-8020}"

rm -f "$BANCO" "$BANCO-wal" "$BANCO-shm"
"$RAIZ/.venv/bin/python" "$RAIZ/web/e2e/semear.py" "$BANCO"
exec "$RAIZ/.venv/bin/personalos" servir --porta "$PORTA" --db "$BANCO"
