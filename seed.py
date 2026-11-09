"""Carrega a estrutura do edital no banco. Idempotente: pode rodar a cada inicialização.

Nunca remove nem sobrescreve progresso do aluno. Só insere blocos/disciplinas/assuntos que
ainda não existem e cria a linha de progresso `nao_iniciado` para cada assunto novo.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .. import config
from ..db import to_iso, utcnow


def carregar_edital(conn: sqlite3.Connection, arquivo: Path | None = None) -> dict[str, int]:
    arquivo = arquivo or (config.SEED_DIR / "edital_2026.json")
    dados = json.loads(arquivo.read_text(encoding="utf-8"))
    agora = to_iso(utcnow())
    novos = {"blocos": 0, "disciplinas": 0, "assuntos": 0}

    for b in dados["blocos"]:
        existente = conn.execute("SELECT id FROM blocos WHERE codigo = ?", (b["codigo"],)).fetchone()
        if existente:
            bloco_id = existente["id"]
        else:
            cur = conn.execute(
                "INSERT INTO blocos (codigo, nome, ordem, num_questoes, eliminatorio, minimo_acertos_pct)"
                " VALUES (?,?,?,?,?,?)",
                (b["codigo"], b["nome"], b["ordem"], b["num_questoes"],
                 1 if b["eliminatorio"] else 0, b["minimo_acertos_pct"]),
            )
            bloco_id = cur.lastrowid
            novos["blocos"] += 1

        for d in b["disciplinas"]:
            existente = conn.execute("SELECT id FROM disciplinas WHERE codigo = ?", (d["codigo"],)).fetchone()
            if existente:
                disciplina_id = existente["id"]
            else:
                cur = conn.execute(
                    "INSERT INTO disciplinas (bloco_id, codigo, nome, ordem, num_questoes, prioridade, descricao_edital)"
                    " VALUES (?,?,?,?,?,?,?)",
                    (bloco_id, d["codigo"], d["nome"], d["ordem"], d["num_questoes"],
                     d["prioridade"], d.get("descricao_edital")),
                )
                disciplina_id = cur.lastrowid
                novos["disciplinas"] += 1

            for ordem, a in enumerate(d["assuntos"], start=1):
                existente = conn.execute(
                    "SELECT id FROM assuntos WHERE disciplina_id = ? AND ordem = ? AND titulo = ?",
                    (disciplina_id, ordem, a["titulo"]),
                ).fetchone()
                if existente:
                    continue
                cur = conn.execute(
                    "INSERT INTO assuntos (disciplina_id, ref_edital, titulo, texto_edital, ordem)"
                    " VALUES (?,?,?,?,?)",
                    (disciplina_id, a["ref"], a["titulo"], a["texto"], ordem),
                )
                conn.execute(
                    "INSERT INTO progresso_assunto (assunto_id, status, atualizado_em) VALUES (?, 'nao_iniciado', ?)",
                    (cur.lastrowid, agora),
                )
                novos["assuntos"] += 1
    conn.commit()
    return novos
