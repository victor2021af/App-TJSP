import sqlite3
from datetime import timedelta
from pathlib import Path

import pytest

from app import db as dbmod
from app.errors import Invalido, NaoEncontrado
from app.services import backup, conteudo, estudo
from conftest import utc

T0 = utc(2026, 11, 8, 12, 0, 0)


def _status(db_path, assunto_id):
    c = dbmod.connect(db_path)
    try:
        return c.execute("SELECT status FROM progresso_assunto WHERE assunto_id=?", (assunto_id,)).fetchone()[0]
    finally:
        c.close()


def test_criar_listar_e_restaurar_desfaz_alteracoes(conn, db_path, tmp_path):
    pasta = tmp_path / "bk"
    a = conn.execute("SELECT id FROM assuntos LIMIT 1").fetchone()["id"]
    conteudo.definir_status(conn, a, "estudado")
    arq = backup.criar_backup(db_path, pasta, now=T0)
    assert arq.name == "tjsp-20261108-120000.db"
    assert [i["nome"] for i in backup.listar(pasta)] == [arq.name]

    conteudo.definir_status(conn, a, "dominado")         # alteração posterior ao backup
    r = backup.restaurar(arq.name, db_path, pasta, now=T0 + timedelta(minutes=5))
    assert _status(db_path, a) == "estudado"
    assert r["backup_de_seguranca"].startswith("pre-restauracao-")
    # o estado "dominado" anterior à restauração continua recuperável
    seg = pasta / r["backup_de_seguranca"]
    c = sqlite3.connect(seg)
    assert c.execute("SELECT status FROM progresso_assunto WHERE assunto_id=?", (a,)).fetchone()[0] == "dominado"
    c.close()


def test_backup_inclui_sessao_de_estudo_aberta(conn, db_path, tmp_path):
    s = estudo.iniciar(conn, objetivo="X", now=T0)
    conn.commit()
    arq = backup.criar_backup(db_path, tmp_path / "bk", now=T0)
    c = sqlite3.connect(arq)
    assert c.execute("SELECT objetivo FROM sessoes_estudo WHERE id=?", (s["id"],)).fetchone()[0] == "X"
    c.close()


@pytest.mark.parametrize("nome", ["../../etc/passwd", "tjsp-1.db", "qualquer.db", "tjsp-20261108-120000.db/../x"])
def test_restaurar_rejeita_nomes_perigosos(db_path, tmp_path, nome):
    with pytest.raises(Invalido):
        backup.restaurar(nome, db_path, tmp_path)


def test_restaurar_backup_inexistente_ou_corrompido(conn, db_path, tmp_path):
    pasta = tmp_path / "bk"
    pasta.mkdir()
    with pytest.raises(NaoEncontrado):
        backup.restaurar("tjsp-20260101-000000.db", db_path, pasta)
    (pasta / "tjsp-20260101-000001.db").write_bytes(b"isto nao e um sqlite" * 100)
    with pytest.raises(Invalido):
        backup.restaurar("tjsp-20260101-000001.db", db_path, pasta)
    # banco de outro programa (sem as tabelas do app) também é recusado
    outro = pasta / "tjsp-20260101-000002.db"
    c = sqlite3.connect(outro); c.execute("CREATE TABLE x (a)"); c.commit(); c.close()
    with pytest.raises(Invalido):
        backup.restaurar(outro.name, db_path, pasta)
    # nada disso alterou o banco vivo
    assert dbmod.connect(db_path).execute("SELECT COUNT(*) FROM blocos").fetchone()[0] == 3


def test_poda_mantem_os_mais_recentes_e_preserva_pre_restauracao(conn, db_path, tmp_path):
    pasta = tmp_path / "bk"
    for i in range(5):
        backup.criar_backup(db_path, pasta, now=T0 + timedelta(minutes=i))
    backup.criar_backup(db_path, pasta, "pre-restauracao", T0)
    assert backup.podar(pasta, manter=2) == 3
    nomes = [i["nome"] for i in backup.listar(pasta)]
    assert len([n for n in nomes if n.startswith("tjsp-")]) == 2
    assert any(n.startswith("pre-restauracao-") for n in nomes)


def test_backup_automatico_so_quando_necessario(conn, db_path, tmp_path):
    pasta = tmp_path / "bk"
    primeiro = backup.backup_automatico_se_necessario(db_path, pasta, horas=24, now=T0)
    assert primeiro is not None
    assert backup.backup_automatico_se_necessario(db_path, pasta, horas=24, now=T0) is None
    futuro = utc(2026, 11, 8, 12) + timedelta(hours=48)
    import os, time
    os.utime(primeiro, (time.time() - 48 * 3600, time.time() - 48 * 3600))
    assert backup.backup_automatico_se_necessario(db_path, pasta, horas=24, now=futuro) is not None
