import sqlite3

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ..db import get_conn, utcnow
from ..deps import usuario_atual
from ..services import estudo

router = APIRouter(prefix="/api/estudo", tags=["estudo"], dependencies=[Depends(usuario_atual)])


class NovaSessao(BaseModel):
    disciplina_id: int | None = None
    assunto_id: int | None = None
    objetivo: str | None = Field(default=None, max_length=300)


class Conclusao(BaseModel):
    objetivo_cumprido: bool | None = None
    observacao: str | None = Field(default=None, max_length=1000)


def _saida(s: sqlite3.Row) -> dict:
    d = dict(s)
    d["segundos_decorridos"] = estudo.segundos_decorridos(s, utcnow())
    d["cronometro_correndo"] = s["em_execucao_desde"] is not None
    return d


@router.get("/sessao-ativa")
def sessao_ativa(conn: sqlite3.Connection = Depends(get_conn)) -> dict | None:
    s = estudo.ativa(conn)
    return _saida(s) if s else None


@router.post("/sessoes", status_code=201)
def iniciar(dados: NovaSessao, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    return _saida(estudo.iniciar(conn, disciplina_id=dados.disciplina_id, assunto_id=dados.assunto_id,
                                 objetivo=dados.objetivo))


@router.post("/sessoes/{sessao_id}/pausar")
def pausar(sessao_id: int, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    return _saida(estudo.pausar(conn, sessao_id))


@router.post("/sessoes/{sessao_id}/retomar")
def retomar(sessao_id: int, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    return _saida(estudo.retomar(conn, sessao_id))


@router.post("/sessoes/{sessao_id}/finalizar")
def finalizar(sessao_id: int, dados: Conclusao, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    return _saida(estudo.finalizar(conn, sessao_id, objetivo_cumprido=dados.objetivo_cumprido,
                                   observacao=dados.observacao))


@router.get("/sessoes")
def historico(limite: int = 50, conn: sqlite3.Connection = Depends(get_conn)) -> list[dict]:
    return [dict(r) for r in estudo.historico(conn, limite)]
