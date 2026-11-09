import sqlite3

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..db import get_conn
from ..deps import usuario_atual
from ..services import conteudo

router = APIRouter(prefix="/api", tags=["conteudo"], dependencies=[Depends(usuario_atual)])


class NovoStatus(BaseModel):
    status: str


@router.get("/conteudo")
def arvore(conn: sqlite3.Connection = Depends(get_conn)) -> list[dict]:
    return conteudo.arvore(conn)


@router.get("/disciplinas/{disciplina_id}/assuntos")
def assuntos(disciplina_id: int, conn: sqlite3.Connection = Depends(get_conn)) -> list[dict]:
    return conteudo.assuntos_da_disciplina(conn, disciplina_id)


@router.put("/assuntos/{assunto_id}/status")
def definir_status(assunto_id: int, dados: NovoStatus, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    return conteudo.definir_status(conn, assunto_id, dados.status)
