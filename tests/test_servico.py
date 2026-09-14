"""O serviço de usuário que faz o PersonalOS abrir sem terminal.

Não dá para testar aqui que ele sobe no login — isso só se prova reiniciando a
máquina. O que dá para mecanizar é o que costuma quebrar em silêncio: unidade
com diretiva errada, caminho de executável que não existe, e sandbox que
esqueceu de liberar o diretório de dados.
"""
from configparser import ConfigParser
from pathlib import Path

import pytest

SETUP = Path(__file__).resolve().parents[1] / "setup"


@pytest.fixture
def unidade() -> ConfigParser:
    # interpolation=None: o systemd usa %h para "home", e o ConfigParser trataria
    # o % como sintaxe própria.
    parser = ConfigParser(strict=False, interpolation=None)
    # systemd aceita chaves repetidas e diferencia maiúsculas; o ConfigParser não
    # pode normalizar o nome, senão 'ExecStart' viraria 'execstart'.
    parser.optionxform = str  # type: ignore[method-assign]
    parser.read(SETUP / "personalos.service", encoding="utf-8")
    return parser


def test_o_instalador_reescreve_o_caminho_do_executavel(unidade):
    """O erro nº1 desse tipo de arquivo é o caminho que só existia na máquina de
    quem escreveu. A defesa não é o arquivo versionado estar certo — é o
    instalador reescrever o ExecStart com o venv que ele mesmo acabou de validar.
    """
    instalador = (SETUP / "instalar.sh").read_text(encoding="utf-8")

    assert "s|^ExecStart=.*|ExecStart=$VENV servir|" in instalador
    assert 'if [[ ! -x "$VENV" ]]' in instalador, "instalador precisa recusar venv inexistente"
    assert unidade["Service"]["ExecStart"].endswith("/bin/personalos servir")


def test_o_sandbox_libera_o_diretorio_de_dados(unidade):
    """ProtectSystem=strict deixa o disco todo somente leitura. Sem liberar o
    diretório de dados, o serviço sobe e falha na primeira escrita — o pior modo
    de falhar, porque parece que funcionou."""
    assert unidade["Service"]["ProtectSystem"] == "strict"
    assert ".local/share/personalos" in unidade["Service"]["ReadWritePaths"]


def test_a_unidade_nao_pede_privilegio(unidade):
    """É um programa pessoal em loopback: não há razão para escalar privilégio."""
    assert unidade["Service"]["NoNewPrivileges"] == "yes"


def test_o_atalho_abre_a_interface_e_nao_o_terminal(unidade):
    atalho = (SETUP / "personalos.desktop").read_text(encoding="utf-8")

    assert "Terminal=false" in atalho
    assert "127.0.0.1:8000/app/" in atalho


def test_o_atalho_usa_o_icone_proprio_e_ele_existe():
    """Ícone genérico do sistema some no meio de dezenas iguais. E `Icon=` que
    aponta pra arquivo inexistente falha calada: o menu mostra um quadrado vazio."""
    atalho = (SETUP / "personalos.desktop").read_text(encoding="utf-8")

    assert "Icon=personalos" in atalho
    assert (SETUP / "personalos.svg").exists()
