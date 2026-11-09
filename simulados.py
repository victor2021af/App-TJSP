"""Simulados. O completo segue a distribuição do EDITAL 2026 (70 questões), usando só questões com gabarito."""
from __future__ import annotations

import random
import sqlite3

from ..db import from_iso, to_iso, utcnow
from ..errors import Conflito, Invalido, NaoEncontrado
from . import questoes as svc_q

# (rótulo, códigos de disciplina do banco, quantidade) — Edital 02/2026, Cap. da prova objetiva.
DISTRIBUICAO_EDITAL = [
    ("Língua Portuguesa", ["portugues"], 16),
    ("Conhecimentos em Direito", ["direito_penal", "direito_processual_penal", "direito_processual_civil",
                                   "direito_constitucional", "direito_administrativo", "legislacao_interna"], 30),
    ("Atualidades", ["atualidades"], 4),
    ("Matemática", ["matematica"], 4),
    ("Informática", ["informatica"], 9),
    ("Raciocínio Lógico", ["raciocinio_logico"], 7),
]
assert sum(n for *_, n in DISTRIBUICAO_EDITAL) == 70


def _candidatas(conn, codigos, somente_oficiais, excluir_feitas) -> list[int]:
    marcas = ",".join("?" * len(codigos))
    sql = f"""SELECT q.id FROM questoes q JOIN disciplinas d ON d.id=q.disciplina_id
              WHERE d.codigo IN ({marcas}) AND q.gabarito IS NOT NULL"""
    if somente_oficiais:
        sql += " AND q.origem='oficial'"
    if excluir_feitas:
        sql += " AND q.id NOT IN (SELECT questao_id FROM tentativas)"
    return [r[0] for r in conn.execute(sql, codigos)]


def montar_completo(conn: sqlite3.Connection, *, somente_oficiais: bool = True, tempo_limite_min: int = 210,
                    prioriza_inéditas: bool = True, semente: int | None = None, now=None) -> dict:
    rng = random.Random(semente)
    escolhidas: list[int] = []
    faltas = []
    for rotulo, codigos, n in DISTRIBUICAO_EDITAL:
        cand = _candidatas(conn, codigos, somente_oficiais, prioriza_inéditas) if prioriza_inéditas else []
        if len(cand) < n:  # completa com já feitas, se necessário
            todas = _candidatas(conn, codigos, somente_oficiais, False)
            cand = cand + [i for i in todas if i not in cand]
        if len(cand) < n:
            faltas.append(f"{rotulo}: precisa de {n}, há {len(cand)} com gabarito")
            continue
        escolhidas += rng.sample(cand, n)
    if faltas:
        raise Conflito("Banco insuficiente para o simulado completo (com gabarito comprovado): " + "; ".join(faltas))
    return _criar(conn, "Simulado completo (70 questões — distribuição do edital 2026)", "completo",
                  escolhidas, somente_oficiais, tempo_limite_min * 60, now)


def montar_por_disciplina(conn: sqlite3.Connection, codigo: str, quantidade: int, *, somente_oficiais: bool = True,
                          semente: int | None = None, now=None) -> dict:
    if quantidade < 1:
        raise Invalido("Quantidade inválida.")
    cand = _candidatas(conn, [codigo], somente_oficiais, False)
    if len(cand) < quantidade:
        raise Conflito(f"Há só {len(cand)} questões com gabarito nessa disciplina.")
    ids = random.Random(semente).sample(cand, quantidade)
    return _criar(conn, f"Simulado — {codigo}", "disciplina", ids, somente_oficiais, None, now)


def _criar(conn, titulo, tipo, ids, so_oficiais, tempo_seg, now) -> dict:
    agora = to_iso(now or utcnow())
    cur = conn.execute("INSERT INTO simulados (titulo, tipo, somente_oficiais, tempo_limite_seg, iniciado_em) VALUES (?,?,?,?,?)",
                       (titulo, tipo, int(so_oficiais), tempo_seg, agora))
    conn.executemany("INSERT INTO simulado_questoes VALUES (?,?,?)", [(cur.lastrowid, q, i + 1) for i, q in enumerate(ids)])
    return {"simulado_id": cur.lastrowid, "titulo": titulo, "total": len(ids), "tempo_limite_seg": tempo_seg}


def obter(conn: sqlite3.Connection, simulado_id: int) -> dict:
    s = conn.execute("SELECT * FROM simulados WHERE id=?", (simulado_id,)).fetchone()
    if not s:
        raise NaoEncontrado("Simulado não encontrado.")
    qs = conn.execute("SELECT questao_id, posicao FROM simulado_questoes WHERE simulado_id=? ORDER BY posicao", (simulado_id,)).fetchall()
    respondidas = {r["questao_id"]: r["alternativa"] for r in conn.execute(
        "SELECT questao_id, alternativa FROM tentativas WHERE simulado_id=?", (simulado_id,))}
    return dict(s) | {"questoes": [{"posicao": r["posicao"], "questao_id": r["questao_id"],
                                    "resposta": respondidas.get(r["questao_id"])} for r in qs]}


def responder(conn, simulado_id: int, questao_id: int, alternativa: str, tempo_segundos: int | None = None, now=None) -> dict:
    s = obter(conn, simulado_id)
    if s["finalizado_em"]:
        raise Conflito("Simulado já finalizado.")
    if questao_id not in {q["questao_id"] for q in s["questoes"]}:
        raise Invalido("Questão não pertence a este simulado.")
    if conn.execute("SELECT 1 FROM tentativas WHERE simulado_id=? AND questao_id=?", (simulado_id, questao_id)).fetchone():
        raise Conflito("Questão já respondida neste simulado.")
    # no simulado o gabarito NÃO é devolvido durante a prova
    r = svc_q.responder(conn, questao_id, alternativa, tempo_segundos=tempo_segundos, contexto="simulado",
                        simulado_id=simulado_id, now=now)
    return {"registrada": True, "tentativa_id": r["tentativa_id"]}


def finalizar(conn: sqlite3.Connection, simulado_id: int, now=None) -> dict:
    s = obter(conn, simulado_id)
    if s["finalizado_em"]:
        raise Conflito("Simulado já finalizado.")
    agora = now or utcnow()
    usados = int((agora - from_iso(s["iniciado_em"])).total_seconds())
    conn.execute("UPDATE simulados SET finalizado_em=?, segundos_usados=? WHERE id=?", (to_iso(agora), usados, simulado_id))
    return resultado(conn, simulado_id)


def resultado(conn: sqlite3.Connection, simulado_id: int) -> dict:
    s = obter(conn, simulado_id)
    linhas = conn.execute(
        """SELECT d.codigo, d.nome, COUNT(sq.questao_id) AS total,
                  SUM(CASE WHEN t.correta=1 THEN 1 ELSE 0 END) AS acertos,
                  SUM(CASE WHEN t.id IS NULL THEN 1 ELSE 0 END) AS em_branco
           FROM simulado_questoes sq JOIN questoes q ON q.id=sq.questao_id JOIN disciplinas d ON d.id=q.disciplina_id
           LEFT JOIN tentativas t ON t.questao_id=sq.questao_id AND t.simulado_id=sq.simulado_id
           WHERE sq.simulado_id=? GROUP BY d.id ORDER BY d.id""", (simulado_id,)).fetchall()
    por = [dict(r) | {"acertos": r["acertos"] or 0} for r in linhas]
    ac = sum(r["acertos"] for r in por)
    out = {"simulado_id": simulado_id, "titulo": s["titulo"], "total": len(s["questoes"]), "acertos": ac,
           "em_branco": sum(r["em_branco"] or 0 for r in por), "segundos_usados": s["segundos_usados"], "por_disciplina": por}
    if s["tipo"] == "completo":
        # Critérios do edital: mínimo de 50% nos blocos I e II (eliminatórios).
        def soma(cods):
            sel = [r for r in por if r["codigo"] in cods]
            return sum(r["acertos"] for r in sel), sum(r["total"] for r in sel)
        a1, t1 = soma(["portugues"])
        a2, t2 = soma(DISTRIBUICAO_EDITAL[1][1])
        out["blocos"] = {
            "I_lingua_portuguesa": {"acertos": a1, "total": t1, "minimo": t1 / 2, "atingiu_minimo": a1 >= t1 / 2},
            "II_direito": {"acertos": a2, "total": t2, "minimo": t2 / 2, "atingiu_minimo": a2 >= t2 / 2},
        }
        out["observacao"] = "Mínimo de 50% nos Blocos I e II é regra do edital; a nota final mínima (5 pontos) considera os três blocos."
    return out
