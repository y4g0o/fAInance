from pathlib import Path

from personalos.nucleo.config import caminho_banco, diretorio_config, diretorio_dados


def test_diretorio_config_usa_xdg(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert diretorio_config() == tmp_path / "personalos"


def test_diretorio_config_default_sem_xdg(monkeypatch):
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    assert diretorio_config() == Path.home() / ".config" / "personalos"


def test_diretorio_dados_usa_xdg(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert diretorio_dados() == tmp_path / "personalos"


def test_diretorio_dados_default_sem_xdg(monkeypatch):
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    assert diretorio_dados() == Path.home() / ".local" / "share" / "personalos"


def test_caminho_banco_fica_dentro_do_diretorio_de_dados(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert caminho_banco() == tmp_path / "personalos" / "personalos.db"
