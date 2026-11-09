import socket
import sqlite3

from fastapi import APIRouter, Depends

from ..db import get_conn
from ..deps import usuario_atual
from ..services import configuracoes
from ..services.painel import painel as calcular_painel

router = APIRouter(prefix="/api", tags=["painel"], dependencies=[Depends(usuario_atual)])


@router.get("/painel")
def painel(conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    return calcular_painel(conn)


@router.get("/configuracoes")
def obter_configuracoes(conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    return configuracoes.obter_todas(conn)


@router.put("/configuracoes")
def atualizar_configuracoes(valores: dict, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    return configuracoes.atualizar(conn, valores)


@router.get("/rede")
def rede() -> dict:
    """Endereços do computador na rede local, para abrir o app no celular."""
    try:
        _, _, ips = socket.gethostbyname_ex(socket.gethostname())
    except OSError:
        ips = []
    return {"enderecos_locais": sorted({ip for ip in ips if not ip.startswith("127.")})}
