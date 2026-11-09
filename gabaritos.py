"""Gabaritos oficiais: leitura, armazenamento separado e aplicação conferida às questões.

Nada é aplicado automaticamente: provas antigas não trazem versão/caderno, e um gabarito de outra versão ou
de outra data de aplicação marcaria questões como certas/erradas ao contrário. Por isso `aplicar` exige um
texto de conferência (ex.: "4 questões de Matemática recalculadas") e que o gabarito tenha o mesmo total.
"""
from __future__ import annotations

import re
import sqlite3

from ..db import to_iso, utcnow
from ..errors import Conflito, Invalido, NaoEncontrado

PAR = re.compile(r"(?<!\d)(\d{1,3})\s*[-–]\s*([A-E])(?![A-Za-z])")
VERSAO = re.compile(r"^\s*VERS[ÃA]O\s+(\d+)\s*$", re.I)


def parse_gabarito(texto: str) -> dict[str, dict[int, str]]:
    """Retorna {versao: {numero: letra}}. Sem marcador de versão, usa '1'. Duplicatas na mesma versão -> erro."""
    versoes: dict[str, dict[int, str]] = {}
    atual = "1"
    for linha in texto.splitlines():
        m = VERSAO.match(linha)
        if m:
            atual = m.group(1)
            versoes.setdefault(atual, {})
            continue
        for num, letra in PAR.findall(linha):
            n = int(num)
            d = versoes.setdefault(atual, {})
            if n in d and d[n] != letra:
                raise Invalido(f"Número {n} aparece com letras diferentes na versão {atual}.")
            d[n] = letra
    return {v: d for v, d in versoes.items() if d}


def armazenar(conn: sqlite3.Connection, texto: str, *, descricao: str, data_prova: str | None = None,
              origem: str | None = None, sha256: str | None = None, esperado: int = 100) -> list[dict]:
    """Guarda cada versão como um gabarito não vinculado. Rejeita versão incompleta (≠ esperado)."""
    versoes = parse_gabarito(texto)
    if not versoes:
        raise Invalido("Nenhum par 'número - letra' encontrado.")
    saida = []
    for versao, resp in versoes.items():
        if sorted(resp) != list(range(1, esperado + 1)):
            faltam = sorted(set(range(1, esperado + 1)) - set(resp))
            raise Invalido(f"Versão {versao} incompleta: {len(resp)} respostas; faltam {faltam[:10]}.")
        if sha256 and conn.execute("SELECT 1 FROM gabaritos WHERE sha256=? AND versao=?", (sha256, versao)).fetchone():
            continue
        cur = conn.execute(
            "INSERT INTO gabaritos (descricao, data_prova, versao, total, origem, sha256, importado_em) VALUES (?,?,?,?,?,?,?)",
            (descricao, data_prova, versao, len(resp), origem, sha256, to_iso(utcnow())),
        )
        conn.executemany("INSERT INTO gabarito_respostas VALUES (?,?,?)", [(cur.lastrowid, n, l) for n, l in resp.items()])
        saida.append({"gabarito_id": cur.lastrowid, "versao": versao, "total": len(resp)})
    return saida


def listar(conn: sqlite3.Connection) -> list[dict]:
    return [dict(r) for r in conn.execute(
        """SELECT g.*, d.nome_arquivo AS prova FROM gabaritos g LEFT JOIN documentos d ON d.id = g.documento_id
           ORDER BY g.data_prova, g.id""")]


def aplicar(conn: sqlite3.Connection, gabarito_id: int, documento_id: int, conferencia: str) -> dict:
    """Copia as letras para as questões da prova (por numero_original). Só preenche questões sem gabarito."""
    if len((conferencia or "").strip()) < 10:
        raise Invalido("Descreva como o vínculo foi conferido (mín. 10 caracteres).")
    g = conn.execute("SELECT * FROM gabaritos WHERE id=?", (gabarito_id,)).fetchone()
    if not g:
        raise NaoEncontrado("Gabarito não encontrado.")
    if g["documento_id"] is not None:
        raise Conflito("Este gabarito já foi aplicado a uma prova.")
    if not conn.execute("SELECT 1 FROM documentos WHERE id=? AND tipo='prova'", (documento_id,)).fetchone():
        raise NaoEncontrado("Prova não encontrada.")
    n_q = conn.execute("SELECT COUNT(*) FROM questoes WHERE documento_id=?", (documento_id,)).fetchone()[0]
    if n_q != g["total"]:
        raise Conflito(f"A prova tem {n_q} questões e o gabarito {g['total']}; não vou aplicar.")
    ja = conn.execute("SELECT COUNT(*) FROM questoes WHERE documento_id=? AND gabarito IS NOT NULL", (documento_id,)).fetchone()[0]
    if ja:
        raise Conflito("A prova já tem respostas gravadas; remova-as antes de aplicar outro gabarito.")
    cur = conn.execute(
        """UPDATE questoes SET gabarito = (SELECT letra FROM gabarito_respostas r WHERE r.gabarito_id=? AND r.numero=questoes.numero_original),
               gabarito_id = ?, precisa_revisao_manual = 0,
               motivo_revisao = NULL
           WHERE documento_id=? AND numero_original IS NOT NULL AND gabarito IS NULL
             AND NOT EXISTS (SELECT 1 FROM alternativas a WHERE a.questao_id=questoes.id GROUP BY a.questao_id HAVING COUNT(*)<>5)""",
        (gabarito_id, gabarito_id, documento_id),
    )
    conn.execute("UPDATE gabaritos SET documento_id=?, aplicado_em=?, conferencia=? WHERE id=?",
                 (documento_id, to_iso(utcnow()), conferencia.strip(), gabarito_id))
    # questões com extração duvidosa continuam para revisão manual
    conn.execute("""UPDATE questoes SET precisa_revisao_manual=1, motivo_revisao='extração duvidosa (alternativas ≠ 5)'
                    WHERE documento_id=? AND gabarito IS NULL""", (documento_id,))
    return {"questoes_atualizadas": cur.rowcount}
