import sqlite3

import pytest

from app import db as dbmod
from app.migrate import apply_migrations, pendentes, versao_atual
from app.services.seed import carregar_edital


def test_migracoes_aplicam_e_sao_idempotentes(db_path):
    c = dbmod.connect(db_path)
    assert apply_migrations(c) == ["0001_nucleo", "0002_questoes_e_avaliacoes", "0003_gabaritos", "0004_ia"]
    assert apply_migrations(c) == []
    assert versao_atual(c) == "0004_ia"
    assert pendentes(c) == []


def test_migracao_com_erro_nao_deixa_meia_aplicacao(tmp_path, db_path):
    pasta = tmp_path / "mig"
    pasta.mkdir()
    (pasta / "0001_ok.sql").write_text("CREATE TABLE a (x INTEGER);")
    (pasta / "0002_ruim.sql").write_text("CREATE TABLE b (x INTEGER); CREATE TABLE a (x INTEGER);")
    c = dbmod.connect(db_path)
    with pytest.raises(sqlite3.Error):
        apply_migrations(c, pasta)
    tabelas = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "a" in tabelas and "b" not in tabelas
    assert versao_atual(c) == "0001_ok"


def test_estrutura_do_edital_2026(conn):
    blocos = {b["codigo"]: b for b in conn.execute("SELECT * FROM blocos")}
    assert {k: v["num_questoes"] for k, v in blocos.items()} == {"I": 16, "II": 30, "III": 24}
    assert sum(b["num_questoes"] for b in blocos.values()) == 70
    # Blocos I e II eliminatórios com 50%; Bloco III só classificatório.
    assert (blocos["I"]["eliminatorio"], blocos["I"]["minimo_acertos_pct"]) == (1, 50)
    assert (blocos["II"]["eliminatorio"], blocos["II"]["minimo_acertos_pct"]) == (1, 50)
    assert (blocos["III"]["eliminatorio"], blocos["III"]["minimo_acertos_pct"]) == (0, None)


def test_questoes_por_disciplina_do_bloco_iii_somam_24(conn):
    n = conn.execute(
        "SELECT SUM(d.num_questoes) FROM disciplinas d JOIN blocos b ON b.id=d.bloco_id WHERE b.codigo='III'"
    ).fetchone()[0]
    assert n == 24
    por_codigo = {r["codigo"]: r["num_questoes"] for r in conn.execute("SELECT codigo, num_questoes FROM disciplinas")}
    assert por_codigo["atualidades"] == 4 and por_codigo["matematica"] == 4
    assert por_codigo["informatica"] == 9 and por_codigo["raciocinio_logico"] == 7
    assert por_codigo["portugues"] == 16


def test_direito_tem_as_seis_divisoes_do_edital(conn):
    codigos = [r["codigo"] for r in conn.execute(
        "SELECT d.codigo FROM disciplinas d JOIN blocos b ON b.id=d.bloco_id WHERE b.codigo='II' ORDER BY d.ordem")]
    assert codigos == ["direito_penal", "direito_processual_penal", "direito_processual_civil",
                       "direito_constitucional", "direito_administrativo", "legislacao_interna"]
    # O edital não divide as 30 questões entre as disciplinas; não inventamos essa divisão.
    assert all(r["num_questoes"] is None for r in conn.execute(
        "SELECT num_questoes FROM disciplinas WHERE codigo LIKE 'direito_%' OR codigo='legislacao_interna'"))


def test_portugues_tem_os_13_itens_e_matematica_os_13(conn):
    def n(cod):
        return conn.execute("SELECT COUNT(*) FROM assuntos a JOIN disciplinas d ON d.id=a.disciplina_id WHERE d.codigo=?", (cod,)).fetchone()[0]
    assert n("portugues") == 13
    assert n("matematica") == 13


def test_todo_assunto_tem_texto_do_edital_e_progresso_inicial(conn):
    assert conn.execute("SELECT COUNT(*) FROM assuntos WHERE texto_edital IS NULL OR texto_edital = ''").fetchone()[0] == 0
    total = conn.execute("SELECT COUNT(*) FROM assuntos").fetchone()[0]
    nao_iniciados = conn.execute("SELECT COUNT(*) FROM progresso_assunto WHERE status='nao_iniciado'").fetchone()[0]
    assert total == nao_iniciados > 0


def test_seed_nao_duplica_nem_apaga_progresso(conn):
    a = conn.execute("SELECT id FROM assuntos LIMIT 1").fetchone()["id"]
    conn.execute("UPDATE progresso_assunto SET status='dominado' WHERE assunto_id=?", (a,))
    conn.commit()
    antes = conn.execute("SELECT COUNT(*) FROM assuntos").fetchone()[0]
    assert carregar_edital(conn) == {"blocos": 0, "disciplinas": 0, "assuntos": 0}
    assert conn.execute("SELECT COUNT(*) FROM assuntos").fetchone()[0] == antes
    assert conn.execute("SELECT status FROM progresso_assunto WHERE assunto_id=?", (a,)).fetchone()[0] == "dominado"
