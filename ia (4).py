"""Professor IA, quadrinhos, redações e fontes na web."""
import base64
import binascii
import sqlite3

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from ..db import get_conn
from ..deps import usuario_atual
from ..errors import Invalido
from ..services import fontes_web, gabaritos, ia, importador, professor, redacao

router = APIRouter(prefix="/api", tags=["ia"], dependencies=[Depends(usuario_atual)])


class Pergunta(BaseModel):
    pergunta: str = Field(max_length=4000)


class Quadrinhos(BaseModel):
    regenerar: bool = False


class EnvioRedacao(BaseModel):
    imagem_base64: str = Field(max_length=12_000_000)
    tema: str | None = Field(default=None, max_length=500)


class Correcao(BaseModel):
    autorizo_envio: bool = False


class Busca(BaseModel):
    consulta: str = Field(min_length=3, max_length=200)


class ImportarUrl(BaseModel):
    url: str
    tipo: str                   # prova | gabarito
    descricao: str = Field(min_length=3, max_length=200)
    data_prova: str | None = None
    total_questoes: int = Field(default=70, ge=1, le=200)


@router.get("/ia/estado")
def estado() -> dict:
    return ia.estado()


@router.post("/professor/conversar")
def conversar(d: Pergunta, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    return professor.conversar(conn, d.pergunta)


@router.get("/professor/historico")
def historico(conn: sqlite3.Connection = Depends(get_conn)) -> list[dict]:
    return professor.historico(conn)


@router.post("/questoes/{questao_id}/quadrinhos")
def quadrinhos(questao_id: int, d: Quadrinhos, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    return professor.quadrinhos(conn, questao_id, d.regenerar)


@router.get("/redacoes")
def redacoes(conn: sqlite3.Connection = Depends(get_conn)) -> list[dict]:
    return redacao.listar(conn)


@router.post("/redacoes")
def enviar(d: EnvioRedacao, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    try:
        dados = base64.b64decode(d.imagem_base64.split(",")[-1], validate=True)
    except (binascii.Error, ValueError):
        raise Invalido("Imagem inválida.") from None
    return redacao.salvar_envio(conn, dados, d.tema)


@router.get("/redacoes/prompt")
def prompt(tema: str | None = None) -> dict:
    return {"prompt": redacao.prompt_para_copiar(tema)}


@router.get("/redacoes/{redacao_id}")
def ver(redacao_id: int, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    return redacao.obter(conn, redacao_id)


@router.get("/redacoes/{redacao_id}/imagem")
def imagem(redacao_id: int, conn: sqlite3.Connection = Depends(get_conn)):
    caminho, tipo = redacao.caminho_da_imagem(conn, redacao_id)
    return FileResponse(caminho, media_type=tipo)


@router.post("/redacoes/{redacao_id}/corrigir")
def corrigir(redacao_id: int, d: Correcao, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    return redacao.corrigir(conn, redacao_id, autorizo_envio=d.autorizo_envio)


@router.post("/fontes/buscar")
def buscar(d: Busca) -> list[dict]:
    return fontes_web.buscar(d.consulta)


@router.post("/fontes/importar-url")
def importar_url(d: ImportarUrl, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    """Baixa um PDF de domínio permitido. Prova -> questões sem gabarito; gabarito -> guardado SEM vínculo."""
    import hashlib
    dados = fontes_web.baixar_pdf(d.url)
    sha = hashlib.sha256(dados).hexdigest()
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as t:
        p = Path(t) / "arquivo.pdf"
        p.write_bytes(dados)
        texto = importador.extrair_texto_pdf(p)
    if d.tipo == "gabarito":
        return {"gabaritos": gabaritos.armazenar(conn, texto, descricao=d.descricao, data_prova=d.data_prova,
                                                 origem=d.url, sha256=sha, esperado=d.total_questoes)}
    if d.tipo == "prova":
        qs = importador.parse_prova(texto)
        return importador.gravar_prova(conn, qs, titulo=d.descricao, sha256=sha, nome_arquivo=d.descricao)
    raise Invalido("tipo deve ser 'prova' ou 'gabarito'.")
