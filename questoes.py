"""Banco de questões: listagem com filtros, resposta, favoritas e estatísticas.

Regra central: só se corrige uma questão que tenha gabarito comprovado. Sem gabarito, a resposta é recusada
(não se inventa certo/errado).
"""
from __future__ import annotations

import sqlite3

from ..db import to_iso, utcnow
from ..errors import Conflito, Invalido, NaoEncontrado

TIPOS_ERRO = {"falta_conhecimento", "interpretacao", "desatencao", "confusao_conceitos", "calculo", "regra", "tempo"}


def _bool(v) -> bool:
    return bool(v)


def listar(conn: sqlite3.Connection, *, disciplina: str | None = None, origem: str | None = None,
           documento_id: int | None = None, somente_com_gabarito: bool = False, favoritas: bool = False,
           erradas: bool = False, nao_respondidas: bool = False, busca: str | None = None,
           limite: int = 50, deslocamento: int = 0) -> dict:
    onde, par = ["1=1"], []
    if disciplina:
        onde.append("d.codigo = ?"); par.append(disciplina)
    if origem:
        if origem not in ("oficial", "ia", "manual"):
            raise Invalido("Origem inválida.")
        onde.append("q.origem = ?"); par.append(origem)
    if documento_id:
        onde.append("q.documento_id = ?"); par.append(documento_id)
    if somente_com_gabarito:
        onde.append("q.gabarito IS NOT NULL")
    if favoritas:
        onde.append("q.id IN (SELECT questao_id FROM questoes_favoritas)")
    if erradas:
        onde.append("""q.id IN (SELECT t.questao_id FROM tentativas t WHERE t.correta = 0 AND t.id =
                       (SELECT MAX(id) FROM tentativas WHERE questao_id = t.questao_id))""")
    if nao_respondidas:
        onde.append("q.id NOT IN (SELECT questao_id FROM tentativas)")
    if busca:
        onde.append("(q.enunciado LIKE ? OR q.texto_apoio LIKE ?)"); par += [f"%{busca}%"] * 2
    base = f"FROM questoes q LEFT JOIN disciplinas d ON d.id = q.disciplina_id WHERE {' AND '.join(onde)}"
    total = conn.execute(f"SELECT COUNT(*) {base}", par).fetchone()[0]
    limite = max(1, min(limite, 200))
    linhas = conn.execute(
        f"""SELECT q.id, q.origem, q.ano, q.numero_original, q.enunciado, d.codigo AS disciplina, d.nome AS disciplina_nome,
                   (q.gabarito IS NOT NULL) AS tem_gabarito, q.precisa_revisao_manual,
                   (q.id IN (SELECT questao_id FROM questoes_favoritas)) AS favorita
            {base} ORDER BY q.documento_id, q.numero_original, q.id LIMIT ? OFFSET ?""", par + [limite, deslocamento]).fetchall()
    itens = []
    for r in linhas:
        i = dict(r)
        i["enunciado"] = i["enunciado"][:200]
        i["tem_gabarito"], i["favorita"] = _bool(i["tem_gabarito"]), _bool(i["favorita"])
        itens.append(i)
    return {"total": total, "itens": itens}


def obter(conn: sqlite3.Connection, questao_id: int, *, com_gabarito: bool = False) -> dict:
    q = conn.execute(
        """SELECT q.*, d.codigo AS disciplina, d.nome AS disciplina_nome, doc.nome_arquivo AS documento
           FROM questoes q LEFT JOIN disciplinas d ON d.id=q.disciplina_id LEFT JOIN documentos doc ON doc.id=q.documento_id
           WHERE q.id=?""", (questao_id,)).fetchone()
    if not q:
        raise NaoEncontrado("Questão não encontrada.")
    r = dict(q)
    r["tem_gabarito"] = r["gabarito"] is not None
    if not com_gabarito:  # o gabarito só sai depois de responder (ver `responder`)
        r.pop("gabarito", None); r.pop("justificativa", None)
    r["alternativas"] = [dict(a) | ({} if com_gabarito else {"explicacao": None}) for a in conn.execute(
        "SELECT letra, texto, explicacao FROM alternativas WHERE questao_id=? ORDER BY letra", (questao_id,))]
    r["favorita"] = conn.execute("SELECT 1 FROM questoes_favoritas WHERE questao_id=?", (questao_id,)).fetchone() is not None
    return r


def responder(conn: sqlite3.Connection, questao_id: int, alternativa: str, *, tempo_segundos: int | None = None,
              contexto: str = "estudo", simulado_id: int | None = None, tipo_erro: str | None = None, now=None) -> dict:
    alternativa = (alternativa or "").upper()
    if alternativa not in tuple("ABCDE"):
        raise Invalido("Alternativa deve ser A, B, C, D ou E.")
    if tipo_erro is not None and tipo_erro not in TIPOS_ERRO:
        raise Invalido("Tipo de erro inválido.")
    if tempo_segundos is not None and tempo_segundos < 0:
        raise Invalido("Tempo inválido.")
    q = conn.execute("SELECT id, gabarito, justificativa FROM questoes WHERE id=?", (questao_id,)).fetchone()
    if not q:
        raise NaoEncontrado("Questão não encontrada.")
    if q["gabarito"] is None:
        raise Conflito("Esta questão ainda não tem gabarito comprovado; não é possível corrigi-la.")
    correta = int(alternativa == q["gabarito"])
    agora = to_iso(now or utcnow())
    cur = conn.execute(
        """INSERT INTO tentativas (questao_id, alternativa, correta, tempo_segundos, contexto, simulado_id, tipo_erro, respondida_em)
           VALUES (?,?,?,?,?,?,?,?)""",
        (questao_id, alternativa, correta, tempo_segundos, contexto, simulado_id, tipo_erro if not correta else None, agora))
    return {"tentativa_id": cur.lastrowid, "correta": bool(correta), "gabarito": q["gabarito"], "justificativa": q["justificativa"]}


def favoritar(conn: sqlite3.Connection, questao_id: int, valor: bool, now=None) -> dict:
    if not conn.execute("SELECT 1 FROM questoes WHERE id=?", (questao_id,)).fetchone():
        raise NaoEncontrado("Questão não encontrada.")
    if valor:
        conn.execute("INSERT OR IGNORE INTO questoes_favoritas VALUES (?,?)", (questao_id, to_iso(now or utcnow())))
    else:
        conn.execute("DELETE FROM questoes_favoritas WHERE questao_id=?", (questao_id,))
    return {"favorita": valor}


def estatisticas(conn: sqlite3.Connection) -> dict:
    """Desempenho real por disciplina (só tentativas existentes; sem dados -> listas vazias)."""
    por = conn.execute(
        """SELECT d.codigo, d.nome, COUNT(*) AS feitas, SUM(t.correta) AS acertos
           FROM tentativas t JOIN questoes q ON q.id=t.questao_id JOIN disciplinas d ON d.id=q.disciplina_id
           GROUP BY d.id ORDER BY d.id""").fetchall()
    erros = conn.execute("SELECT tipo_erro, COUNT(*) n FROM tentativas WHERE correta=0 AND tipo_erro IS NOT NULL GROUP BY 1").fetchall()
    tot = conn.execute("SELECT COUNT(*), COALESCE(SUM(correta),0) FROM tentativas").fetchone()
    return {
        "feitas": tot[0], "acertos": tot[1], "aproveitamento": round(100 * tot[1] / tot[0], 1) if tot[0] else None,
        "por_disciplina": [{"codigo": r["codigo"], "nome": r["nome"], "feitas": r["feitas"], "acertos": r["acertos"],
                            "aproveitamento": round(100 * r["acertos"] / r["feitas"], 1)} for r in por],
        "tipos_de_erro": {r["tipo_erro"]: r["n"] for r in erros},
    }
