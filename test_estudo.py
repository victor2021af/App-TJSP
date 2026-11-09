import sqlite3
from datetime import timedelta

import pytest

from app.errors import Conflito, Invalido, NaoEncontrado
from app.services import estudo
from conftest import utc

T0 = utc(2026, 11, 8, 12, 0, 0)


def _assunto(conn, codigo="portugues"):
    return conn.execute(
        "SELECT a.id, a.disciplina_id FROM assuntos a JOIN disciplinas d ON d.id=a.disciplina_id WHERE d.codigo=? ORDER BY a.ordem LIMIT 1",
        (codigo,)).fetchone()


def test_cronometro_conta_apenas_tempo_efetivo_com_pausa(conn):
    s = estudo.iniciar(conn, objetivo="Crase", now=T0)
    assert estudo.segundos_decorridos(s, T0 + timedelta(minutes=10)) == 600
    s = estudo.pausar(conn, s["id"], now=T0 + timedelta(minutes=10))
    # 30 min parado não contam
    assert estudo.segundos_decorridos(s, T0 + timedelta(minutes=40)) == 600
    s = estudo.retomar(conn, s["id"], now=T0 + timedelta(minutes=40))
    s = estudo.finalizar(conn, s["id"], objetivo_cumprido=True, now=T0 + timedelta(minutes=45))
    assert s["status"] == "concluida"
    assert s["segundos_acumulados"] == 600 + 300
    assert s["objetivo_cumprido"] == 1 and s["em_execucao_desde"] is None


def test_finalizar_estando_pausada_nao_soma_tempo_parado(conn):
    s = estudo.iniciar(conn, now=T0)
    estudo.pausar(conn, s["id"], now=T0 + timedelta(minutes=5))
    s = estudo.finalizar(conn, s["id"], now=T0 + timedelta(hours=3))
    assert s["segundos_acumulados"] == 300


def test_so_uma_sessao_aberta_por_vez(conn):
    s = estudo.iniciar(conn, now=T0)
    with pytest.raises(Conflito):
        estudo.iniciar(conn, now=T0)
    estudo.pausar(conn, s["id"], now=T0)
    with pytest.raises(Conflito):  # pausada também é "aberta"
        estudo.iniciar(conn, now=T0)
    estudo.finalizar(conn, s["id"], now=T0)
    assert estudo.iniciar(conn, now=T0)["id"] != s["id"]


def test_o_banco_tambem_impede_duas_sessoes_abertas(conn):
    estudo.iniciar(conn, now=T0)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO sessoes_estudo (status, iniciada_em) VALUES ('pausada','2026-11-08T12:00:00Z')")


def test_transicoes_invalidas(conn):
    s = estudo.iniciar(conn, now=T0)
    with pytest.raises(Conflito):
        estudo.retomar(conn, s["id"], now=T0)
    estudo.pausar(conn, s["id"], now=T0)
    with pytest.raises(Conflito):
        estudo.pausar(conn, s["id"], now=T0)
    estudo.finalizar(conn, s["id"], now=T0)
    with pytest.raises(Conflito):
        estudo.finalizar(conn, s["id"], now=T0)
    with pytest.raises(NaoEncontrado):
        estudo.pausar(conn, 9999)


def test_assunto_define_disciplina_e_marca_em_andamento_sem_rebaixar(conn):
    a = _assunto(conn)
    s = estudo.iniciar(conn, assunto_id=a["id"], now=T0)
    assert s["disciplina_id"] == a["disciplina_id"]
    st = lambda: conn.execute("SELECT status FROM progresso_assunto WHERE assunto_id=?", (a["id"],)).fetchone()[0]
    assert st() == "em_andamento"
    estudo.finalizar(conn, s["id"], now=T0)
    conn.execute("UPDATE progresso_assunto SET status='dominado' WHERE assunto_id=?", (a["id"],))
    conn.commit()
    estudo.iniciar(conn, assunto_id=a["id"], now=T0 + timedelta(days=1))
    assert st() == "dominado"  # estudar de novo não rebaixa


def test_assunto_de_outra_disciplina_e_rejeitado(conn):
    a = _assunto(conn, "portugues")
    outra = conn.execute("SELECT id FROM disciplinas WHERE codigo='matematica'").fetchone()["id"]
    with pytest.raises(Invalido):
        estudo.iniciar(conn, disciplina_id=outra, assunto_id=a["id"], now=T0)
    with pytest.raises(NaoEncontrado):
        estudo.iniciar(conn, assunto_id=999999, now=T0)


def test_estado_sobrevive_a_reabrir_o_banco(conn, db_path):
    from app import db as dbmod
    s = estudo.iniciar(conn, objetivo="Persistência", now=T0)
    conn.commit()
    novo = dbmod.connect(db_path)  # simula reiniciar o servidor / outro aparelho
    ativa = estudo.ativa(novo)
    assert ativa["id"] == s["id"] and ativa["objetivo"] == "Persistência"
    assert estudo.segundos_decorridos(ativa, T0 + timedelta(minutes=3)) == 180
    novo.close()
