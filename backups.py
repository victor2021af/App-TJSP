import sqlite3

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..db import connect, get_conn
from ..deps import usuario_atual
from ..errors import Invalido
from ..services import auditoria, backup

router = APIRouter(prefix="/api/backups", tags=["backup"])


class ConfirmarRestauracao(BaseModel):
    confirmar: bool = False


@router.get("")
def listar(_=Depends(usuario_atual)) -> list[dict]:
    return backup.listar()


@router.post("", status_code=201)
def criar(usuario=Depends(usuario_atual), conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    arquivo = backup.criar_backup()
    backup.podar()
    auditoria.registrar(conn, "backup_criado", usuario_id=usuario["id"], entidade="backup", entidade_id=arquivo.name)
    return {"nome": arquivo.name}


@router.post("/{nome}/restaurar")
def restaurar(nome: str, dados: ConfirmarRestauracao, usuario=Depends(usuario_atual)) -> dict:
    if not dados.confirmar:
        raise Invalido("Restaurar substitui todos os dados atuais. Envie confirmar=true para prosseguir.")
    resultado = backup.restaurar(nome)
    novo = connect()  # o banco foi substituído; registra a ação na conexão nova
    try:
        auditoria.registrar(novo, "backup_restaurado", usuario_id=None, entidade="backup", entidade_id=nome,
                            detalhes=f"por {usuario['nome'] or 'uso local'}; segurança: {resultado['backup_de_seguranca']}")
    finally:
        novo.close()
    return {**resultado, "aviso": "Se o backup for mais antigo que o seu login, será preciso entrar novamente."}
