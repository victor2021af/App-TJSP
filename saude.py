import sqlite3

from fastapi import APIRouter, Depends

from .. import config
from ..db import get_conn
from ..migrate import versao_atual

router = APIRouter(prefix="/api", tags=["saude"])


@router.get("/saude")
def saude(conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    ok = conn.execute("SELECT 1").fetchone()[0] == 1
    return {"status": "ok" if ok else "erro", "versao_app": config.APP_VERSION,
            "versao_esquema": versao_atual(conn)}
