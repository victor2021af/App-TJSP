import sqlite3

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from .. import config
from ..db import get_conn
from ..deps import token_da_requisicao, usuario_atual
from ..errors import NaoAutenticado
from ..services import auth, auditoria

router = APIRouter(prefix="/api/auth", tags=["auth"])
_limitador = auth.LimitadorDeLogin(maximo=5, janela_seg=300)


class Credenciais(BaseModel):
    nome: str = Field(min_length=1, max_length=80)
    senha: str = Field(min_length=1, max_length=200)


@router.get("/estado")
def estado(conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    """Público: diz ao frontend se precisa mostrar a tela de primeiro acesso ou de login."""
    return {"configurado": auth.configurado(conn), "auth_ativa": config.AUTH_ENABLED}


@router.post("/configurar", status_code=201)
def configurar(dados: Credenciais, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    uid = auth.criar_usuario(conn, dados.nome, dados.senha)
    auditoria.registrar(conn, "usuario_criado", usuario_id=uid, entidade="usuarios", entidade_id=uid)
    return {"token": auth.entrar(conn, dados.nome, dados.senha), "nome": dados.nome.strip()}


@router.post("/entrar")
def entrar(dados: Credenciais, request: Request, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    chave = request.client.host if request.client else "desconhecido"
    _limitador.verificar(chave)
    try:
        token = auth.entrar(conn, dados.nome, dados.senha)
    except NaoAutenticado:
        _limitador.registrar_falha(chave)
        raise
    _limitador.limpar(chave)
    return {"token": token, "nome": dados.nome.strip()}


@router.post("/sair", status_code=204)
def sair(conn: sqlite3.Connection = Depends(get_conn), token: str | None = Depends(token_da_requisicao)) -> None:
    auth.sair(conn, token)


@router.get("/eu")
def eu(usuario=Depends(usuario_atual)) -> dict:
    return {"id": usuario["id"], "nome": usuario["nome"]}
