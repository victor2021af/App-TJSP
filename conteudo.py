"""Conteúdo programático (estrutura do edital) e status de aprendizado por assunto."""
from __future__ import annotations

import sqlite3
from datetime import datetime

from ..db import to_iso, utcnow
from ..errors import Invalido, NaoEncontrado

STATUS_VALIDOS = ("nao_iniciado", "em_andamento", "estudado", "em_revisao", "dominado", "necessita_reforco")


def arvore(conn: sqlite3.Connection) -> list[dict]:
    blocos = []
    for b in conn.execute("SELECT * FROM blocos ORDER BY ordem"):
        disciplinas = []
        for d in conn.execute("SELECT * FROM disciplinas WHERE bloco_id = ? ORDER BY ordem", (b["id"],)):
            contagem = {s: 0 for s in STATUS_VALIDOS}
            for linha in conn.execute(
                "SELECT p.status, COUNT(*) AS n FROM assuntos a JOIN progresso_assunto p ON p.assunto_id = a.id"
                " WHERE a.disciplina_id = ? GROUP BY p.status", (d["id"],)):
                contagem[linha["status"]] = linha["n"]
            disciplinas.append({**dict(d), "assuntos_total": sum(contagem.values()), "status_contagem": contagem})
        blocos.append({**dict(b), "eliminatorio": bool(b["eliminatorio"]), "disciplinas": disciplinas})
    return blocos


def assuntos_da_disciplina(conn: sqlite3.Connection, disciplina_id: int) -> list[dict]:
    if not conn.execute("SELECT 1 FROM disciplinas WHERE id = ?", (disciplina_id,)).fetchone():
        raise NaoEncontrado("Disciplina não encontrada.")
    linhas = conn.execute(
        "SELECT a.id, a.parent_id, a.ref_edital, a.titulo, a.texto_edital, a.ordem, p.status, p.atualizado_em"
        " FROM assuntos a JOIN progresso_assunto p ON p.assunto_id = a.id"
        " WHERE a.disciplina_id = ? ORDER BY a.ordem", (disciplina_id,)).fetchall()
    return [dict(l) for l in linhas]


def definir_status(conn: sqlite3.Connection, assunto_id: int, status: str, now: datetime | None = None) -> dict:
    if status not in STATUS_VALIDOS:
        raise Invalido(f"Status inválido. Use um destes: {', '.join(STATUS_VALIDOS)}.")
    if not conn.execute("SELECT 1 FROM assuntos WHERE id = ?", (assunto_id,)).fetchone():
        raise NaoEncontrado("Assunto não encontrado.")
    agora = to_iso(now or utcnow())
    conn.execute(
        "INSERT INTO progresso_assunto (assunto_id, status, atualizado_em) VALUES (?,?,?)"
        " ON CONFLICT(assunto_id) DO UPDATE SET status = excluded.status, atualizado_em = excluded.atualizado_em",
        (assunto_id, status, agora),
    )
    if status in ("estudado", "em_revisao"):
        from . import revisao  # evita import circular

        revisao.agendar_se_necessario(conn, assunto_id, now=now)
    conn.commit()
    return {"assunto_id": assunto_id, "status": status, "atualizado_em": agora}
