"""Banco de questões, gabaritos, revisões espaçadas e simulados."""
import sqlite3

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from ..db import get_conn
from ..deps import usuario_atual
from ..services import gabaritos, questoes, revisao, simulados

router = APIRouter(prefix="/api", tags=["banco"], dependencies=[Depends(usuario_atual)])


class Resposta(BaseModel):
    alternativa: str
    tempo_segundos: int | None = Field(default=None, ge=0, le=36000)
    tipo_erro: str | None = None


class Favorita(BaseModel):
    favorita: bool


class AplicarGabarito(BaseModel):
    documento_id: int
    conferencia: str = Field(min_length=10, max_length=500)


class NovoSimulado(BaseModel):
    tipo: str = "completo"            # completo | disciplina
    disciplina: str | None = None
    quantidade: int | None = Field(default=None, ge=1, le=100)
    somente_oficiais: bool = True


class RespostaSimulado(BaseModel):
    questao_id: int
    alternativa: str
    tempo_segundos: int | None = Field(default=None, ge=0, le=36000)


class ConclusaoRevisao(BaseModel):
    acerto_pct: int | None = Field(default=None, ge=0, le=100)


@router.get("/questoes")
def listar(disciplina: str | None = None, origem: str | None = None, documento_id: int | None = None,
           somente_com_gabarito: bool = False, favoritas: bool = False, erradas: bool = False,
           nao_respondidas: bool = False, busca: str | None = Query(default=None, max_length=100),
           limite: int = 50, deslocamento: int = 0, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    return questoes.listar(conn, disciplina=disciplina, origem=origem, documento_id=documento_id,
                           somente_com_gabarito=somente_com_gabarito, favoritas=favoritas, erradas=erradas,
                           nao_respondidas=nao_respondidas, busca=busca, limite=limite, deslocamento=deslocamento)


@router.get("/questoes/estatisticas")
def estatisticas(conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    return questoes.estatisticas(conn)


@router.get("/questoes/{questao_id}")
def obter(questao_id: int, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    return questoes.obter(conn, questao_id)


@router.post("/questoes/{questao_id}/responder")
def responder(questao_id: int, d: Resposta, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    return questoes.responder(conn, questao_id, d.alternativa, tempo_segundos=d.tempo_segundos, tipo_erro=d.tipo_erro)


@router.put("/questoes/{questao_id}/favorita")
def favoritar(questao_id: int, d: Favorita, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    return questoes.favoritar(conn, questao_id, d.favorita)


@router.get("/documentos")
def documentos(conn: sqlite3.Connection = Depends(get_conn)) -> list[dict]:
    return [dict(r) for r in conn.execute(
        """SELECT d.id, d.nome_arquivo, d.ano, (SELECT COUNT(*) FROM questoes q WHERE q.documento_id=d.id) AS questoes,
                  (SELECT COUNT(*) FROM questoes q WHERE q.documento_id=d.id AND q.gabarito IS NOT NULL) AS com_gabarito
           FROM documentos d WHERE d.tipo='prova' ORDER BY d.ano, d.id""")]


@router.get("/gabaritos")
def gabaritos_lista(conn: sqlite3.Connection = Depends(get_conn)) -> list[dict]:
    return gabaritos.listar(conn)


@router.post("/gabaritos/{gabarito_id}/aplicar")
def aplicar(gabarito_id: int, d: AplicarGabarito, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    return gabaritos.aplicar(conn, gabarito_id, d.documento_id, d.conferencia)


@router.get("/revisoes")
def revisoes(futuras: bool = False, conn: sqlite3.Connection = Depends(get_conn)) -> list[dict]:
    from ..db import utcnow
    return revisao.pendentes(conn, utcnow(), incluir_futuras=futuras)


@router.post("/revisoes/{revisao_id}/concluir")
def concluir(revisao_id: int, d: ConclusaoRevisao, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    return revisao.concluir(conn, revisao_id, d.acerto_pct)


@router.post("/simulados")
def novo_simulado(d: NovoSimulado, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    if d.tipo == "disciplina":
        from ..errors import Invalido
        if not d.disciplina or not d.quantidade:
            raise Invalido("Informe disciplina e quantidade.")
        return simulados.montar_por_disciplina(conn, d.disciplina, d.quantidade, somente_oficiais=d.somente_oficiais)
    return simulados.montar_completo(conn, somente_oficiais=d.somente_oficiais)


@router.get("/simulados")
def simulados_lista(conn: sqlite3.Connection = Depends(get_conn)) -> list[dict]:
    return [dict(r) for r in conn.execute("SELECT id, titulo, tipo, iniciado_em, finalizado_em FROM simulados ORDER BY id DESC")]


@router.get("/simulados/{simulado_id}")
def simulado(simulado_id: int, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    return simulados.obter(conn, simulado_id)


@router.post("/simulados/{simulado_id}/responder")
def simulado_responder(simulado_id: int, d: RespostaSimulado, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    return simulados.responder(conn, simulado_id, d.questao_id, d.alternativa, d.tempo_segundos)


@router.post("/simulados/{simulado_id}/finalizar")
def simulado_finalizar(simulado_id: int, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    return simulados.finalizar(conn, simulado_id)


@router.get("/simulados/{simulado_id}/resultado")
def simulado_resultado(simulado_id: int, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    return simulados.resultado(conn, simulado_id)
