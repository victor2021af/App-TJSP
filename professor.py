"""Meu Professor IA e quadrinhos "ENTENDER ESTA QUESTÃO". Tudo gerado por IA é rotulado como tal."""
from __future__ import annotations

import json
import sqlite3

from ..db import to_iso, utcnow
from ..errors import Invalido, NaoEncontrado
from . import ia, questoes, revisao

REGRAS = (
    "Você é o professor particular de um candidato ao concurso de Escrevente Técnico Judiciário do TJSP (edital 02/2026, banca VUNESP). "
    "Seja exigente, técnico e didático; ensine o raciocínio, não só a resposta. Responda em português do Brasil. "
    "Não invente artigos de lei, números, estatísticas ou fatos; quando não tiver certeza ou o conteúdo depender de material que o aluno não "
    "forneceu, diga isso claramente. Informe que seu conteúdo é gerado por IA e deve ser conferido nas fontes oficiais quando citar norma. "
    "Use apenas o desempenho do aluno que aparece no contexto abaixo; não invente histórico."
)


def contexto_do_aluno(conn: sqlite3.Connection, now=None) -> str:
    est = questoes.estatisticas(conn)
    fracos = conn.execute(
        """SELECT a.titulo, d.nome FROM progresso_assunto p JOIN assuntos a ON a.id=p.assunto_id JOIN disciplinas d ON d.id=a.disciplina_id
           WHERE p.status='necessita_reforco' LIMIT 8""").fetchall()
    rev = revisao.pendentes(conn, now=now)[:8]
    partes = [f"Questões feitas: {est['feitas']}; acertos: {est['acertos']}; aproveitamento: {est['aproveitamento'] if est['aproveitamento'] is not None else 'sem dados'}%."]
    if est["por_disciplina"]:
        partes.append("Por disciplina: " + "; ".join(f"{d['nome']} {d['aproveitamento']}% ({d['feitas']})" for d in est["por_disciplina"]))
    if est["tipos_de_erro"]:
        partes.append("Tipos de erro registrados: " + ", ".join(f"{k}={v}" for k, v in est["tipos_de_erro"].items()))
    if fracos:
        partes.append("Assuntos marcados 'necessita reforço': " + "; ".join(f"{r[1]} — {r[0]}" for r in fracos))
    if rev:
        partes.append("Revisões vencidas/pendentes: " + "; ".join(f"{r['disciplina']} — {r['assunto']}" for r in rev))
    return "\n".join(partes)


def conversar(conn: sqlite3.Connection, pergunta: str, now=None) -> dict:
    pergunta = (pergunta or "").strip()
    if not pergunta or len(pergunta) > 4000:
        raise Invalido("Escreva uma pergunta de até 4000 caracteres.")
    prov = ia.provedor_atual()
    hist = conn.execute("SELECT papel, texto FROM conversas_professor ORDER BY id DESC LIMIT 10").fetchall()[::-1]
    msgs = [{"role": "user" if h["papel"] == "aluno" else "assistant", "content": h["texto"]} for h in hist]
    msgs.append({"role": "user", "content": pergunta})
    resposta = prov.completar(REGRAS + "\n\nCONTEXTO REAL DO ALUNO:\n" + contexto_do_aluno(conn, now), msgs)
    agora = to_iso(now or utcnow())
    conn.execute("INSERT INTO conversas_professor (papel, texto, criado_em) VALUES ('aluno',?,?)", (pergunta, agora))
    conn.execute("INSERT INTO conversas_professor (papel, texto, provedor, criado_em) VALUES ('professor',?,?,?)", (resposta, prov.nome, agora))
    return {"resposta": resposta, "provedor": prov.nome, "gerado_por_ia": True}


def historico(conn: sqlite3.Connection, limite: int = 50) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT papel, texto, criado_em FROM (SELECT * FROM conversas_professor ORDER BY id DESC LIMIT ?) ORDER BY id", (limite,))]


def _validar_quadros(d: dict) -> list[dict]:
    qs = d.get("quadros")
    if not isinstance(qs, list) or not 3 <= len(qs) <= 8:
        raise ia.IaIndisponivel("A IA não devolveu entre 3 e 8 quadros; tente novamente.")
    out = []
    for q in qs:
        if not isinstance(q, dict) or not str(q.get("fala", "")).strip():
            raise ia.IaIndisponivel("Quadro sem fala; tente novamente.")
        out.append({"titulo": str(q.get("titulo", ""))[:80], "cena": str(q.get("cena", ""))[:300],
                    "fala": str(q["fala"])[:500], "destaque": str(q.get("destaque", ""))[:200]})
    return out


def quadrinhos(conn: sqlite3.Connection, questao_id: int, regenerar: bool = False, now=None) -> dict:
    """Explicação em quadrinhos. Só para questão COM gabarito (a IA recebe o gabarito oficial; não o deduz)."""
    q = questoes.obter(conn, questao_id, com_gabarito=True)
    if not q["tem_gabarito"]:
        raise Invalido("A questão ainda não tem gabarito comprovado; não explico para não ensinar a resposta errada.")
    if not regenerar:
        c = conn.execute("SELECT quadros_json, provedor FROM explicacoes_questao WHERE questao_id=?", (questao_id,)).fetchone()
        if c:
            return {"quadros": json.loads(c["quadros_json"]), "provedor": c["provedor"], "gerado_por_ia": True, "do_cache": True}
    alts = "\n".join(f"({a['letra']}) {a['texto']}" for a in q["alternativas"])
    pedido = (
        "Explique a questão abaixo em 4 a 6 quadrinhos didáticos para um adulto estudando para concurso. Estrutura: 1) o que a banca pede; "
        "2) como interpretar; 3) por que a alternativa correta é correta; 4) por que a mais tentadora está errada; 5) regra para guardar. "
        "O GABARITO OFICIAL é a alternativa " + q["gabarito"] + "; não o questione. "
        'Responda SOMENTE em JSON: {"quadros":[{"titulo":"","cena":"descrição curta da cena/personagem","fala":"texto do balão","destaque":"termo ou regra em destaque"}]}.\n\n'
        f"TEXTO-BASE: {q['texto_apoio'] or '(nenhum)'}\nENUNCIADO: {q['enunciado']}\n{alts}"
    )
    prov = ia.provedor_atual()
    quadros = _validar_quadros(ia.extrair_json(prov.completar(REGRAS, [{"role": "user", "content": pedido}], max_tokens=2500)))
    conn.execute("INSERT OR REPLACE INTO explicacoes_questao (questao_id, quadros_json, provedor, criada_em) VALUES (?,?,?,?)",
                 (questao_id, json.dumps(quadros, ensure_ascii=False), prov.nome, to_iso(now or utcnow())))
    return {"quadros": quadros, "provedor": prov.nome, "gerado_por_ia": True, "do_cache": False}
