"""Minhas Redações: foto -> correção por IA com os critérios do EDITAL (Cap. XI), nota apenas estimada.

Privacidade: a imagem só é enviada ao provedor de IA com autorização explícita POR ENVIO (`autorizo_envio=True`).
Sem autorização, nada sai do computador; o aluno pode copiar o prompt e usar onde preferir.
"""
from __future__ import annotations

import json
import secrets
import sqlite3
from pathlib import Path

from .. import config
from ..db import to_iso, utcnow
from ..errors import Conflito, Invalido, NaoEncontrado
from . import ia

TAMANHO_MAX = 8 * 1024 * 1024
CRITERIOS_ARQUIVO = config.SEED_DIR / "redacao_criterios_edital.txt"
AVISO_NOTA = ("Nota ESTIMADA por IA, sem valor oficial: o edital não publica pontuação por critério nem grade de correção. "
              "Referência do edital: escala 0–40, aprovação com 24 pontos ou mais (19,2 nas vagas reservadas).")


def _tipo_da_imagem(dados: bytes) -> str:
    if dados[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if dados[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if dados[:4] == b"RIFF" and dados[8:12] == b"WEBP":
        return "image/webp"
    raise Invalido("Envie uma imagem JPG, PNG ou WEBP.")


def salvar_envio(conn: sqlite3.Connection, dados: bytes, tema: str | None, now=None) -> dict:
    if not dados:
        raise Invalido("Arquivo vazio.")
    if len(dados) > TAMANHO_MAX:
        raise Invalido("Imagem maior que 8 MB.")
    tipo = _tipo_da_imagem(dados)  # conteúdo, não extensão enviada pelo cliente
    nome = secrets.token_hex(16) + {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}[tipo]
    config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    (config.UPLOAD_DIR / nome).write_bytes(dados)
    cur = conn.execute("INSERT INTO redacoes (tema, arquivo_imagem, criada_em) VALUES (?,?,?)",
                       ((tema or "").strip()[:500] or None, nome, to_iso(now or utcnow())))
    return {"redacao_id": cur.lastrowid}


def caminho_da_imagem(conn: sqlite3.Connection, redacao_id: int) -> tuple[Path, str]:
    r = conn.execute("SELECT arquivo_imagem FROM redacoes WHERE id=?", (redacao_id,)).fetchone()
    if not r or not r["arquivo_imagem"]:
        raise NaoEncontrado("Redação não encontrada.")
    p = (config.UPLOAD_DIR / r["arquivo_imagem"]).resolve()
    if config.UPLOAD_DIR.resolve() not in p.parents or not p.exists():
        raise NaoEncontrado("Arquivo da redação não encontrado.")
    return p, _tipo_da_imagem(p.read_bytes()[:16])


def instrucoes() -> str:
    criterios = CRITERIOS_ARQUIVO.read_text(encoding="utf-8")
    return (
        "Você é corretor de redação do concurso de Escrevente Técnico Judiciário do TJSP (VUNESP). Avalie SOMENTE pelos critérios do edital "
        "transcritos abaixo (tema; estrutura: gênero/coerência; língua; coesão) e verifique cada situação de nota zero do item 8 e de texto "
        "não escrito do item 9. Não invente critérios nem pesos oficiais. Não reescreva a redação inteira. "
        "Se a imagem estiver ilegível, diga e não avalie o que não conseguir ler. Seja exigente e específico: cite trechos.\n\n"
        "EDITAL:\n" + criterios
    )


FORMATO = (
    'Responda SOMENTE em JSON: {"transcricao":"texto lido da imagem","linhas_estimadas":0,'
    '"criterios":{"tema":{"parecer":"","problemas":[]},"estrutura":{"parecer":"","problemas":[]},"lingua":{"parecer":"","problemas":[]},"coesao":{"parecer":"","problemas":[]}},'
    '"situacoes_de_nota_zero":[{"item":"8a","ocorre":false,"justificativa":""}],'
    '"nota_estimada_0_a_40":0,"pontos_a_melhorar":[""],"proximo_exercicio":""}'
)


def prompt_para_copiar(tema: str | None) -> str:
    return instrucoes() + f"\n\nTEMA/PROPOSTA: {tema or '(informe a proposta)'}\n\nAnexe a foto da redação. " + FORMATO


def corrigir(conn: sqlite3.Connection, redacao_id: int, *, autorizo_envio: bool, now=None) -> dict:
    if autorizo_envio is not True:
        raise Conflito("É preciso autorizar explicitamente o envio da imagem ao provedor de IA.")
    caminho, tipo = caminho_da_imagem(conn, redacao_id)
    prov = ia.provedor_atual()
    tema = conn.execute("SELECT tema FROM redacoes WHERE id=?", (redacao_id,)).fetchone()["tema"]
    pedido = f"TEMA/PROPOSTA informados pelo aluno: {tema or '(não informado)'}\nCorrija a redação da imagem anexa.\n{FORMATO}"
    try:
        rel = ia.extrair_json(prov.completar(instrucoes(), [{"role": "user", "content": pedido}],
                                             imagem=ia.Imagem(caminho.read_bytes(), tipo), max_tokens=3500))
    except Exception as e:
        conn.execute("UPDATE redacoes SET status='erro', aviso=? WHERE id=?", (str(e)[:300], redacao_id))
        raise
    nota = rel.get("nota_estimada_0_a_40")
    nota = float(nota) if isinstance(nota, (int, float)) and 0 <= nota <= 40 else None
    zero = any(isinstance(s, dict) and s.get("ocorre") is True for s in rel.get("situacoes_de_nota_zero", []))
    if zero:
        nota = 0.0
    conn.execute(
        """UPDATE redacoes SET provedor_ia=?, relatorio_json=?, texto_transcrito=?, nota_estimada=?, autorizou_envio=1,
                                status='corrigida', aviso=? WHERE id=?""",
        (prov.nome, json.dumps(rel, ensure_ascii=False), str(rel.get("transcricao", ""))[:20000], nota, AVISO_NOTA, redacao_id))
    return {"redacao_id": redacao_id, "relatorio": rel, "nota_estimada": nota, "aviso": AVISO_NOTA, "provedor": prov.nome, "gerado_por_ia": True}


def listar(conn: sqlite3.Connection) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT id, tema, status, nota_estimada, provedor_ia, criada_em FROM redacoes ORDER BY id DESC")]


def obter(conn: sqlite3.Connection, redacao_id: int) -> dict:
    r = conn.execute("SELECT * FROM redacoes WHERE id=?", (redacao_id,)).fetchone()
    if not r:
        raise NaoEncontrado("Redação não encontrada.")
    d = dict(r)
    d["relatorio"] = json.loads(d.pop("relatorio_json")) if d.get("relatorio_json") else None
    d.pop("arquivo_imagem", None)
    return d
