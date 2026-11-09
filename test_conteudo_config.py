import pytest

from app.errors import Invalido, NaoEncontrado
from app.services import configuracoes, conteudo


def test_arvore_traz_blocos_disciplinas_e_contagens(conn):
    arv = conteudo.arvore(conn)
    assert [b["codigo"] for b in arv] == ["I", "II", "III"]
    assert [len(b["disciplinas"]) for b in arv] == [1, 6, 4]
    port = arv[0]["disciplinas"][0]
    assert port["assuntos_total"] == 13 and port["status_contagem"]["nao_iniciado"] == 13


def test_definir_status(conn):
    a = conn.execute("SELECT id FROM assuntos LIMIT 1").fetchone()["id"]
    assert conteudo.definir_status(conn, a, "dominado")["status"] == "dominado"
    with pytest.raises(Invalido):
        conteudo.definir_status(conn, a, "quase")
    with pytest.raises(NaoEncontrado):
        conteudo.definir_status(conn, 999999, "dominado")
    with pytest.raises(NaoEncontrado):
        conteudo.assuntos_da_disciplina(conn, 999999)


def test_configuracoes_validam_entrada(conn):
    assert configuracoes.atualizar(conn, {"meta_diaria_minutos": 90})["meta_diaria_minutos"] == 90
    for ruim in ({"meta_diaria_minutos": -1}, {"meta_diaria_minutos": "90"}, {"meta_diaria_minutos": True},
                 {"disponibilidade_semanal_minutos": [1, 2]}, {"data_inicio_estudos": "ontem"}, {"outra": 1}):
        with pytest.raises(Invalido):
            configuracoes.atualizar(conn, ruim)
    assert configuracoes.obter(conn, "meta_diaria_minutos") == 90   # nada foi alterado pelas inválidas
    configuracoes.atualizar(conn, {"disponibilidade_semanal_minutos": [60, 60, 60, 60, 60, 120, 120]})
    assert configuracoes.obter(conn, "disponibilidade_semanal_minutos")[5] == 120
    configuracoes.atualizar(conn, {"meta_diaria_minutos": None})
    assert configuracoes.obter(conn, "meta_diaria_minutos") is None
