"""Cronômetro de estudo. O estado vive no banco, não no navegador:
fechar a aba, trocar de aparelho ou reiniciar o servidor não perde o tempo contado.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime

from ..db import from_iso, to_iso, utcnow
from ..errors import Conflito, Invalido, NaoEncontrado


def segundos_decorridos(sessao: sqlite3.Row, now: datetime | None = None) -> int:
    now = now or utcnow()
    total = sessao["segundos_acumulados"]
    if sessao["em_execucao_desde"]:
        total += max(0, int((now - from_iso(sessao["em_execucao_desde"])).total_seconds()))
    return total


def _buscar(conn: sqlite3.Connection, sessao_id: int) -> sqlite3.Row:
    linha = conn.execute("SELECT * FROM sessoes_estudo WHERE id = ?", (sessao_id,)).fetchone()
    if not linha:
        raise NaoEncontrado("Sessão de estudo não encontrada.")
    return linha


def ativa(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM sessoes_estudo WHERE status <> 'concluida'").fetchone()


def iniciar(conn: sqlite3.Connection, *, disciplina_id: int | None = None, assunto_id: int | None = None,
            objetivo: str | None = None, now: datetime | None = None) -> sqlite3.Row:
    now = now or utcnow()
    if ativa(conn):
        raise Conflito("Já existe uma sessão de estudo aberta. Finalize-a antes de iniciar outra.")

    if assunto_id is not None:
        assunto = conn.execute("SELECT disciplina_id FROM assuntos WHERE id = ?", (assunto_id,)).fetchone()
        if not assunto:
            raise NaoEncontrado("Assunto não encontrado.")
        if disciplina_id is not None and disciplina_id != assunto["disciplina_id"]:
            raise Invalido("O assunto informado não pertence à disciplina informada.")
        disciplina_id = assunto["disciplina_id"]
    elif disciplina_id is not None:
        if not conn.execute("SELECT 1 FROM disciplinas WHERE id = ?", (disciplina_id,)).fetchone():
            raise NaoEncontrado("Disciplina não encontrada.")

    objetivo = (objetivo or "").strip() or None
    cur = conn.execute(
        "INSERT INTO sessoes_estudo (disciplina_id, assunto_id, objetivo, status, iniciada_em, em_execucao_desde)"
        " VALUES (?,?,?, 'em_andamento', ?, ?)",
        (disciplina_id, assunto_id, objetivo, to_iso(now), to_iso(now)),
    )
    conn.commit()
    if assunto_id is not None:
        # Estudar um assunto pela primeira vez o move para "em andamento"; nunca rebaixa um status existente.
        conn.execute(
            "UPDATE progresso_assunto SET status = 'em_andamento', atualizado_em = ?"
            " WHERE assunto_id = ? AND status = 'nao_iniciado'",
            (to_iso(now), assunto_id),
        )
        conn.commit()
    return _buscar(conn, cur.lastrowid)


def pausar(conn: sqlite3.Connection, sessao_id: int, now: datetime | None = None) -> sqlite3.Row:
    now = now or utcnow()
    s = _buscar(conn, sessao_id)
    if s["status"] != "em_andamento":
        raise Conflito("A sessão não está em andamento.")
    conn.execute(
        "UPDATE sessoes_estudo SET status = 'pausada', segundos_acumulados = ?, em_execucao_desde = NULL WHERE id = ?",
        (segundos_decorridos(s, now), sessao_id),
    )
    conn.commit()
    return _buscar(conn, sessao_id)


def retomar(conn: sqlite3.Connection, sessao_id: int, now: datetime | None = None) -> sqlite3.Row:
    now = now or utcnow()
    s = _buscar(conn, sessao_id)
    if s["status"] != "pausada":
        raise Conflito("A sessão não está pausada.")
    conn.execute(
        "UPDATE sessoes_estudo SET status = 'em_andamento', em_execucao_desde = ? WHERE id = ?",
        (to_iso(now), sessao_id),
    )
    conn.commit()
    return _buscar(conn, sessao_id)


def finalizar(conn: sqlite3.Connection, sessao_id: int, *, objetivo_cumprido: bool | None = None,
              observacao: str | None = None, now: datetime | None = None) -> sqlite3.Row:
    now = now or utcnow()
    s = _buscar(conn, sessao_id)
    if s["status"] == "concluida":
        raise Conflito("A sessão já foi finalizada.")
    conn.execute(
        "UPDATE sessoes_estudo SET status = 'concluida', segundos_acumulados = ?, em_execucao_desde = NULL,"
        " finalizada_em = ?, objetivo_cumprido = ?, observacao = ? WHERE id = ?",
        (segundos_decorridos(s, now), to_iso(now),
         None if objetivo_cumprido is None else int(objetivo_cumprido),
         (observacao or "").strip() or None, sessao_id),
    )
    conn.commit()
    return _buscar(conn, sessao_id)


def historico(conn: sqlite3.Connection, limite: int = 50) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT s.*, d.nome AS disciplina_nome, a.titulo AS assunto_titulo"
        " FROM sessoes_estudo s"
        " LEFT JOIN disciplinas d ON d.id = s.disciplina_id"
        " LEFT JOIN assuntos a ON a.id = s.assunto_id"
        " WHERE s.status = 'concluida' ORDER BY s.finalizada_em DESC LIMIT ?",
        (max(1, min(limite, 500)),),
    ).fetchall()
