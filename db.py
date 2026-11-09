"""Acesso ao SQLite.

A camada é propositalmente fina (sqlite3 da biblioteca padrão + SQL explícito) para que a
migração futura para PostgreSQL seja uma troca localizada neste módulo e nas migrações.
"""
from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path

from . import config


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    path = Path(path) if path else config.DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 15000")
    return conn


def get_conn() -> Iterator[sqlite3.Connection]:
    """Dependência do FastAPI: uma conexão por requisição, com commit/rollback."""
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---- utilitários de tempo (sempre UTC no banco) -------------------------------------

ISO_FMT = "%Y-%m-%dT%H:%M:%SZ"


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def to_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime(ISO_FMT)


def from_iso(value: str) -> datetime:
    return datetime.strptime(value, ISO_FMT).replace(tzinfo=timezone.utc)
