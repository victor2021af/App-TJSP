"""Configurações do aluno (chave/valor). Só chaves conhecidas são aceitas."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from ..db import to_iso, utcnow
from ..errors import Invalido

# chave -> (validador, padrão)
def _minutos(v):
    if not isinstance(v, int) or isinstance(v, bool) or not (0 <= v <= 1440):
        raise Invalido("Informe um número inteiro de minutos entre 0 e 1440.")
    return v


def _dias_semana(v):
    # lista de 7 inteiros (seg..dom) com minutos disponíveis por dia
    if not (isinstance(v, list) and len(v) == 7):
        raise Invalido("Informe 7 valores (segunda a domingo).")
    return [_minutos(x) for x in v]


def _data_iso(v):
    from datetime import date
    try:
        date.fromisoformat(v)
    except (TypeError, ValueError):
        raise Invalido("Use uma data no formato AAAA-MM-DD.")
    return v


CHAVES = {
    "meta_diaria_minutos": (_minutos, None),
    "disponibilidade_semanal_minutos": (_dias_semana, None),
    "data_inicio_estudos": (_data_iso, None),
}


def obter_todas(conn: sqlite3.Connection) -> dict:
    resultado = {chave: padrao for chave, (_, padrao) in CHAVES.items()}
    for l in conn.execute("SELECT chave, valor FROM configuracoes"):
        if l["chave"] in CHAVES:
            resultado[l["chave"]] = json.loads(l["valor"])
    return resultado


def obter(conn: sqlite3.Connection, chave: str):
    return obter_todas(conn).get(chave)


def atualizar(conn: sqlite3.Connection, valores: dict, now: datetime | None = None) -> dict:
    desconhecidas = [k for k in valores if k not in CHAVES]
    if desconhecidas:
        raise Invalido(f"Configuração desconhecida: {', '.join(desconhecidas)}.")
    agora = to_iso(now or utcnow())
    for chave, valor in valores.items():
        if valor is None:
            conn.execute("DELETE FROM configuracoes WHERE chave = ?", (chave,))
            continue
        validado = CHAVES[chave][0](valor)
        conn.execute(
            "INSERT INTO configuracoes (chave, valor, atualizado_em) VALUES (?,?,?)"
            " ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor, atualizado_em = excluded.atualizado_em",
            (chave, json.dumps(validado), agora),
        )
    conn.commit()
    return obter_todas(conn)
