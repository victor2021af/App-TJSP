"""Dependências compartilhadas dos routers."""
from __future__ import annotations

import sqlite3

from fastapi import Depends, Header

from . import config
from .db import get_conn
from .errors import NaoAutenticado
from .services import auth

# Usuário implícito quando o login está desligado (uso pessoal local).
USUARIO_LOCAL = {"id": None, "nome": ""}


def token_da_requisicao(authorization: str | None = Header(default=None)) -> str | None:
    if not authorization:
        return None
    partes = authorization.split(" ", 1)
    if len(partes) != 2 or partes[0].lower() != "bearer":
        raise NaoAutenticado("Cabeçalho de autorização inválido.")
    return partes[1].strip()


def usuario_atual(conn: sqlite3.Connection = Depends(get_conn),
                  token: str | None = Depends(token_da_requisicao)):
    # config.AUTH_ENABLED é lido a cada requisição (permite testar os dois modos).
    if not config.AUTH_ENABLED:
        return USUARIO_LOCAL
    return auth.usuario_do_token(conn, token)
