"""Caminhos de configuração e dados do PersonalOS, seguindo o padrão XDG."""
from __future__ import annotations

import os
from pathlib import Path


def diretorio_config() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))
    return Path(base) / "personalos"


def diretorio_dados() -> Path:
    base = os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))
    return Path(base) / "personalos"


def caminho_banco() -> Path:
    return diretorio_dados() / "personalos.db"


def diretorio_extratos() -> Path:
    """Onde ficam os extratos enviados pela interface.

    Ao lado do banco, não na árvore do projeto: extrato bancário não pode acabar
    versionado por acidente, e um caminho derivado do código-fonte não sobrevive
    ao pacote instalado.
    """
    return diretorio_dados() / "extratos"
