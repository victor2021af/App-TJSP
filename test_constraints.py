import sqlite3

import pytest

AGORA = "2026-11-08T12:00:00Z"


def _questao(conn, **kw):
    campos = dict(origem="manual", enunciado="Enunciado?", criada_em=AGORA)
    campos.update(kw)
    cols = ", ".join(campos)
    marcas = ", ".join("?" for _ in campos)
    cur = conn.execute(f"INSERT INTO questoes ({cols}) VALUES ({marcas})", tuple(campos.values()))
    return cur.lastrowid


def test_questao_oficial_exige_documento_de_origem(conn):
    with pytest.raises(sqlite3.IntegrityError):
        _questao(conn, origem="oficial")
    conn.execute("INSERT INTO documentos (nome_arquivo, tipo, importado_em) VALUES ('p.pdf','prova',?)", (AGORA,))
    assert _questao(conn, origem="oficial", documento_id=1) > 0


def test_gabarito_pode_ser_nulo_mas_nao_invalido(conn):
    assert _questao(conn, gabarito=None) > 0           # gabarito não comprovado
    with pytest.raises(sqlite3.IntegrityError):
        _questao(conn, gabarito="F")


def test_alternativas_somente_a_ate_e_sem_duplicar(conn):
    q = _questao(conn)
    conn.execute("INSERT INTO alternativas (questao_id, letra, texto) VALUES (?,?,?)", (q, "A", "x"))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO alternativas (questao_id, letra, texto) VALUES (?,?,?)", (q, "A", "y"))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO alternativas (questao_id, letra, texto) VALUES (?,?,?)", (q, "F", "y"))


def test_origem_invalida_e_rejeitada(conn):
    with pytest.raises(sqlite3.IntegrityError):
        _questao(conn, origem="inventada")
