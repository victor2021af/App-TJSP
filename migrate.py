"""Migrações SQL versionadas.

Arquivos `NNNN_nome.sql` em app/migrations são aplicados em ordem, cada um dentro de uma
transação, e registrados em `schema_migrations`. Nunca edite uma migração já aplicada:
crie uma nova.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from . import config
from .db import to_iso, utcnow

_NAME = re.compile(r"^(\d{4})_[a-z0-9_]+\.sql$")


def _ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        " versao TEXT PRIMARY KEY, aplicada_em TEXT NOT NULL)"
    )
    conn.commit()


def pendentes(conn: sqlite3.Connection, directory: Path | None = None) -> list[Path]:
    directory = directory or config.MIGRATIONS_DIR
    _ensure_table(conn)
    aplicadas = {r[0] for r in conn.execute("SELECT versao FROM schema_migrations")}
    arquivos = sorted(p for p in directory.glob("*.sql") if _NAME.match(p.name))
    return [p for p in arquivos if p.stem not in aplicadas]


def apply_migrations(conn: sqlite3.Connection, directory: Path | None = None) -> list[str]:
    aplicadas: list[str] = []
    for arquivo in pendentes(conn, directory):
        sql = arquivo.read_text(encoding="utf-8")
        script = (
            "BEGIN;\n"
            f"{sql}\n"
            f"INSERT INTO schema_migrations (versao, aplicada_em) "
            f"VALUES ('{arquivo.stem}', '{to_iso(utcnow())}');\n"
            "COMMIT;"
        )
        try:
            conn.executescript(script)
        except Exception:
            if conn.in_transaction:
                conn.rollback()
            raise
        aplicadas.append(arquivo.stem)
    return aplicadas


def versao_atual(conn: sqlite3.Connection) -> str | None:
    _ensure_table(conn)
    row = conn.execute("SELECT MAX(versao) FROM schema_migrations").fetchone()
    return row[0]
