#!/usr/bin/env bash
# Instala o PersonalOS como aplicativo: sobe no login e abre por um ícone.
#
# Unidade de USUÁRIO, nunca do sistema — roda como você, sem root. O serviço fica
# preso a loopback (o próprio programa recusa outro bind) e o sandbox do systemd
# só libera escrita no diretório de dados.
#
# Desfazer:
#   systemctl --user disable --now personalos
#   rm ~/.config/systemd/user/personalos.service ~/.local/share/applications/personalos.desktop
set -euo pipefail

AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$(dirname "$AQUI")/.venv/bin/personalos"

if [[ ! -x "$VENV" ]]; then
  echo "Não achei o executável em $VENV." >&2
  echo "Crie o ambiente primeiro:  uv venv .venv && uv pip install --python .venv/bin/python -e ." >&2
  exit 1
fi

mkdir -p ~/.config/systemd/user ~/.local/share/applications ~/.local/share/icons/hicolor/scalable/apps
sed "s|^ExecStart=.*|ExecStart=$VENV servir|" "$AQUI/personalos.service" \
  > ~/.config/systemd/user/personalos.service
cp "$AQUI/personalos.desktop" ~/.local/share/applications/personalos.desktop
cp "$AQUI/personalos.svg" ~/.local/share/icons/hicolor/scalable/apps/personalos.svg
gtk-update-icon-cache -f -t ~/.local/share/icons/hicolor 2>/dev/null || true
update-desktop-database ~/.local/share/applications 2>/dev/null || true

systemctl --user daemon-reload
systemctl --user enable --now personalos

echo "Pronto. PersonalOS em http://127.0.0.1:8000/app/ e no menu de aplicativos."
echo "Se algo falhar:  journalctl --user -u personalos -n 50"
