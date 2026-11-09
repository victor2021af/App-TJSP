"""Revisão espaçada por assunto: 24 h, 7 d, 15 d, 30 d, adaptada ao desempenho.

Regras (decisão pedagógica do app, não regra do edital):
- Assunto marcado como estudado -> 1ª revisão em 1 dia.
- Ao concluir uma revisão com acerto informado:
    >= 80%  avança para a próxima etapa (7, 15, 30 dias); após a 30 d o ciclo termina.
    60–79%  repete a mesma etapa com metade do intervalo (mín. 1 dia).
    < 60%   volta à etapa 0 (1 dia) e o assunto passa a 'necessita_reforco'.
- Sem acerto informado, trata-se como 'avança' (o aluno apenas confirmou que revisou).
"""
from __future__ import annotations

import sqlite3
from datetime import timedelta

from ..db import from_iso, to_iso, utcnow
from ..errors import Conflito, Invalido, NaoEncontrado

INTERVALOS_DIAS = [1, 7, 15, 30]


def agendar_se_necessario(conn: sqlite3.Connection, assunto_id: int, now=None) -> bool:
    if conn.execute("SELECT 1 FROM revisoes_agendadas WHERE assunto_id=? AND concluida_em IS NULL", (assunto_id,)).fetchone():
        return False
    agora = now or utcnow()
    conn.execute("INSERT INTO revisoes_agendadas (assunto_id, etapa, devida_em) VALUES (?,0,?)",
                 (assunto_id, to_iso(agora + timedelta(days=INTERVALOS_DIAS[0]))))
    return True


def pendentes(conn: sqlite3.Connection, now=None, incluir_futuras: bool = False) -> list[dict]:
    agora = to_iso(now or utcnow())
    filtro = "" if incluir_futuras else "AND r.devida_em <= ?"
    par = [] if incluir_futuras else [agora]
    linhas = conn.execute(
        f"""SELECT r.id, r.assunto_id, r.etapa, r.devida_em, a.titulo AS assunto, d.nome AS disciplina, d.codigo AS disciplina_codigo
            FROM revisoes_agendadas r JOIN assuntos a ON a.id=r.assunto_id JOIN disciplinas d ON d.id=a.disciplina_id
            WHERE r.concluida_em IS NULL {filtro} ORDER BY r.devida_em""", par).fetchall()
    return [dict(r) | {"atrasada": r["devida_em"] < agora, "intervalo_dias": INTERVALOS_DIAS[r["etapa"]]} for r in linhas]


def concluir(conn: sqlite3.Connection, revisao_id: int, acerto_pct: int | None = None, now=None) -> dict:
    r = conn.execute("SELECT * FROM revisoes_agendadas WHERE id=?", (revisao_id,)).fetchone()
    if not r:
        raise NaoEncontrado("Revisão não encontrada.")
    if r["concluida_em"]:
        raise Conflito("Revisão já concluída.")
    if acerto_pct is not None and not 0 <= acerto_pct <= 100:
        raise Invalido("Acerto deve estar entre 0 e 100.")
    agora = now or utcnow()
    conn.execute("UPDATE revisoes_agendadas SET concluida_em=?, acerto_pct=? WHERE id=?", (to_iso(agora), acerto_pct, revisao_id))
    etapa = r["etapa"]
    proxima: int | None
    dias: int | None = None
    if acerto_pct is not None and acerto_pct < 60:
        proxima, dias = 0, INTERVALOS_DIAS[0]
        conn.execute("""INSERT INTO progresso_assunto (assunto_id, status, atualizado_em) VALUES (?,?,?)
                        ON CONFLICT(assunto_id) DO UPDATE SET status=excluded.status, atualizado_em=excluded.atualizado_em""",
                     (r["assunto_id"], "necessita_reforco", to_iso(agora)))
    elif acerto_pct is not None and acerto_pct < 80:
        proxima, dias = etapa, max(1, INTERVALOS_DIAS[etapa] // 2)
    else:
        proxima = etapa + 1
        if proxima >= len(INTERVALOS_DIAS):
            proxima = None
        else:
            dias = INTERVALOS_DIAS[proxima]
    if proxima is not None:
        conn.execute("INSERT INTO revisoes_agendadas (assunto_id, etapa, devida_em) VALUES (?,?,?)",
                     (r["assunto_id"], proxima, to_iso(agora + timedelta(days=dias))))
    return {"concluida": revisao_id, "proxima_etapa": proxima, "proxima_em_dias": dias, "ciclo_encerrado": proxima is None}
