from sqlalchemy import MetaData

from personalos.nucleo.modulo import Modulo, Vista


def test_vista_tem_nome_e_sql():
    v = Vista(nome="vw_teste_v1", sql="SELECT 1")
    assert v.nome == "vw_teste_v1"
    assert v.sql == "SELECT 1"


def test_modulo_com_vistas():
    v = Vista(nome="vw_teste_v1", sql="SELECT 1")
    m = Modulo(nome="teste", metadata=MetaData(), vistas=(v,))
    assert m.vistas == (v,)


def test_modulo_sem_vistas_por_padrao():
    m = Modulo(nome="teste", metadata=MetaData())
    assert m.vistas == ()


def test_kernel_nao_depende_de_nenhum_modulo():
    """Inversão de dependência, mecanizada.

    O kernel define o contrato; os módulos o implementam. Se `nucleo/` importar
    `modulos/`, a dependência aponta para o lado errado e o kernel deixa de ser
    reutilizável — com uma dezena de módulos previstos, isso viraria um nó
    impossível de desatar. Quem conhece todos os módulos é o composition root
    (`personalos/composicao.py`), que vive na borda.

    Este teste existe porque a regra já foi violada uma vez: `MODULOS` morava em
    `nucleo/registro.py` e importava o manifesto do financas.
    """
    from pathlib import Path

    import personalos.nucleo as nucleo

    infratores = [
        arquivo.name
        for arquivo in Path(nucleo.__file__).parent.rglob("*.py")
        if "personalos.modulos" in arquivo.read_text(encoding="utf-8")
    ]
    assert infratores == [], f"kernel importando módulo: {infratores}"
