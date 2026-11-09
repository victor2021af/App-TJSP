"""Trilha de auditoria para alterações importantes (restauração de backup, configuração, etc.)."""
from __future__ import annotations

import sqlite3

from ..db import to_iso, utcnow


def registrar(conn: sqlite3.Connection, acao: str, *, usuario_id: int | None = None,
              entidade: str | None = None, entidade_id: str | int | None = None,
              detalhes: str | None = None) -> None:
    conn.execute(
        "INSERT INTO auditoria (quando, usuario_id, acao, entidade, entidade_id, detalhes) VALUES (?,?,?,?,?,?)",
        (to_iso(utcnow()), usuario_id, acao, entidade,
         None if entidade_id is None else str(entidade_id), detalhes),
    )
    conn.commit()
