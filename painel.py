"""Indicadores do painel. Tudo é calculado a partir de registros reais.

Regras deliberadas:
- Sem tentativas registradas, o percentual de acertos é `None` (não 0%, não um valor inventado).
- Não existe "probabilidade de aprovação". O indicador de preparo expõe só componentes
  mensuráveis: conteúdo concluído, meta do dia e acertos nas questões.
- "Conteúdo concluído" = assuntos em estudado, em_revisao ou dominado.
"""
from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from .. import config
from ..db import from_iso, utcnow
from . import configuracoes
from .estudo import segundos_decorridos

CONCLUIDOS = ("estudado", "em_revisao", "dominado")


def _data_local(iso: str, tz: ZoneInfo) -> date:
    return from_iso(iso).astimezone(tz).date()


def _sequencia(dias: set[date], hoje: date) -> int:
    """Dias consecutivos de estudo. Se hoje ainda não teve estudo, conta a partir de ontem."""
    cursor = hoje if hoje in dias else hoje - timedelta(days=1)
    n = 0
    while cursor in dias:
        n += 1
        cursor -= timedelta(days=1)
    return n


def painel(conn: sqlite3.Connection, now: datetime | None = None, tz_nome: str | None = None) -> dict:
    now = now or utcnow()
    tz = ZoneInfo(tz_nome or config.DEFAULT_TIMEZONE)
    hoje = now.astimezone(tz).date()

    # ---- tempo estudado -------------------------------------------------------------------
    total = hoje_seg = 0
    por_disciplina: dict[int | None, int] = {}
    dias_com_estudo: set[date] = set()
    for s in conn.execute("SELECT * FROM sessoes_estudo"):
        seg = segundos_decorridos(s, now)
        if seg <= 0:
            continue
        data = _data_local(s["finalizada_em"], tz) if s["finalizada_em"] else hoje
        total += seg
        if data == hoje:
            hoje_seg += seg
        dias_com_estudo.add(data)
        por_disciplina[s["disciplina_id"]] = por_disciplina.get(s["disciplina_id"], 0) + seg

    nomes = {d["id"]: d["nome"] for d in conn.execute("SELECT id, nome FROM disciplinas")}
    horas_por_disciplina = sorted(
        ({"disciplina_id": k, "nome": nomes.get(k, "Sem disciplina"), "segundos": v}
         for k, v in por_disciplina.items()),
        key=lambda x: -x["segundos"],
    )

    # ---- questões ---------------------------------------------------------------------------
    q = conn.execute(
        "SELECT COUNT(*) AS n, COALESCE(SUM(correta),0) AS ok, AVG(tempo_segundos) AS tempo FROM tentativas"
    ).fetchone()
    respondidas, acertos = q["n"], q["ok"]
    questoes = {
        "respondidas": respondidas,
        "acertos": acertos,
        "erros": respondidas - acertos,
        "acerto_pct": round(100 * acertos / respondidas, 1) if respondidas else None,
        "tempo_medio_segundos": round(q["tempo"]) if q["tempo"] is not None else None,
    }

    # ---- conteúdo ---------------------------------------------------------------------------
    contagem = {r["status"]: r["n"] for r in conn.execute(
        "SELECT status, COUNT(*) AS n FROM progresso_assunto GROUP BY status")}
    total_assuntos = sum(contagem.values())
    concluidos = sum(contagem.get(s, 0) for s in CONCLUIDOS)
    conteudo = {
        "total_assuntos": total_assuntos,
        "por_status": contagem,
        "concluido_pct": round(100 * concluidos / total_assuntos, 1) if total_assuntos else None,
    }

    # ---- meta do dia ------------------------------------------------------------------------
    meta_min = configuracoes.obter(conn, "meta_diaria_minutos")
    meta_pct = round(100 * hoje_seg / (meta_min * 60)) if meta_min else None

    # ---- listas -----------------------------------------------------------------------------
    ultimos = [dict(r) for r in conn.execute(
        "SELECT s.id, s.finalizada_em, s.segundos_acumulados, d.nome AS disciplina, a.titulo AS assunto"
        " FROM sessoes_estudo s LEFT JOIN disciplinas d ON d.id = s.disciplina_id"
        " LEFT JOIN assuntos a ON a.id = s.assunto_id"
        " WHERE s.status = 'concluida' AND s.assunto_id IS NOT NULL ORDER BY s.finalizada_em DESC LIMIT 5")]

    revisoes = [dict(r) for r in conn.execute(
        "SELECT r.id, r.assunto_id, a.titulo AS assunto, r.devida_em FROM revisoes_agendadas r"
        " JOIN assuntos a ON a.id = r.assunto_id WHERE r.concluida_em IS NULL ORDER BY r.devida_em LIMIT 5")]

    prioritarias = []
    for d in conn.execute(
        "SELECT d.id, d.nome, d.prioridade, COUNT(p.assunto_id) AS total,"
        " SUM(CASE WHEN p.status IN ('estudado','em_revisao','dominado') THEN 1 ELSE 0 END) AS feitos"
        " FROM disciplinas d JOIN assuntos a ON a.disciplina_id = d.id"
        " JOIN progresso_assunto p ON p.assunto_id = a.id GROUP BY d.id"):
        prioritarias.append({"disciplina_id": d["id"], "nome": d["nome"], "prioridade": d["prioridade"],
                             "concluido_pct": round(100 * d["feitos"] / d["total"], 1) if d["total"] else 0.0})
    prioritarias.sort(key=lambda x: (x["prioridade"], x["concluido_pct"], x["nome"]))

    proximo = conn.execute(
        "SELECT a.id AS assunto_id, a.titulo, d.id AS disciplina_id, d.nome AS disciplina"
        " FROM assuntos a JOIN progresso_assunto p ON p.assunto_id = a.id"
        " JOIN disciplinas d ON d.id = a.disciplina_id JOIN blocos b ON b.id = d.bloco_id"
        " WHERE p.status = 'nao_iniciado'"
        " ORDER BY d.prioridade, b.ordem, d.ordem, a.ordem LIMIT 1").fetchone()

    return {
        "gerado_em": now.isoformat(),
        "fuso_horario": str(tz),
        "estudo": {
            "total_segundos": total,
            "hoje_segundos": hoje_seg,
            "sequencia_dias": _sequencia(dias_com_estudo, hoje),
            "por_disciplina": horas_por_disciplina,
            "meta_diaria_minutos": meta_min,
            "meta_diaria_cumprida_pct": meta_pct,
        },
        "questoes": questoes,
        "conteudo": conteudo,
        "indicador_preparo": {
            "descricao": "Componentes mensuráveis do seu progresso. Não é uma previsão de aprovação.",
            "conteudo_concluido_pct": conteudo["concluido_pct"],
            "meta_do_dia_pct": meta_pct,
            "acerto_pct": questoes["acerto_pct"],
        },
        "ultimos_assuntos": ultimos,
        "proximas_revisoes": revisoes,
        "materias_prioritarias": prioritarias[:3],
        "sugestao_automatica": (
            {**dict(proximo), "motivo": "Primeiro assunto ainda não iniciado, seguindo a prioridade das disciplinas "
                                        "e a ordem do edital (regra automática, não é análise de IA)."}
            if proximo else None
        ),
    }
