"""Importador de provas antigas da VUNESP (texto extraído de PDF -> questões).

Regras de fidelidade:
- NÃO inventa gabarito: toda questão importada fica com gabarito NULL e precisa_revisao_manual=1 até
  que um gabarito oficial seja aplicado (ver services/gabaritos.py).
- Questão que não tem exatamente 5 alternativas A–E é marcada para revisão manual, com o motivo.
- O que o parser não entende é sinalizado, nunca "consertado" em silêncio.
"""
from __future__ import annotations

import hashlib
import re
import sqlite3
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from ..db import to_iso, utcnow

MARCA_PAGINA = re.compile(r"^=====PAGINA (\d+)=====$")
CABECALHO = re.compile(r"^TJSP\d{4}/\d{3}-.*Confidencial até o momento da aplicação\.?$")
CONFIDENCIAL = re.compile(r"^Confidencial até o momento da aplicação\.?$")
NUM_PAGINA = re.compile(r"^\d{1,3}$")
INICIO_QUESTAO = re.compile(r"^(\d{2,3})\.\s+(\S.*)$")
ALTERNATIVA = re.compile(r"^\(([A-E])\)\s*(.*)$")
TEXTO_BASE = re.compile(
    r"^Leia (?:o|os|a|as)\b.*?(?:quest[õo]es|quest[ãa]o)\b.*?(?:n[úu]meros?\s+)?(\d{1,3})\s*(?:a|e|ao)\s*(\d{1,3})", re.I
)
TEXTO_BASE_SIMPLES = re.compile(r"(?:quest[õo]es|quest[ãa]o) de n[úu]meros?\s+(\d{1,3})\s*(?:a|e)\s*(\d{1,3})", re.I)

# título normalizado -> (bloco, disciplina do edital 2026 ou None)
SECOES = {
    "lingua portuguesa": "portugues",
    "direito penal": "direito_penal",
    "direito processual penal": "direito_processual_penal",
    "direito processual civil": "direito_processual_civil",
    "direito constitucional": "direito_constitucional",
    "direito administrativo": "direito_administrativo",
    "atualidades": "atualidades",
    "matematica": "matematica",
    "informatica": "informatica",
    "raciocinio logico": "raciocinio_logico",
}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", s).strip()


@dataclass
class QuestaoImportada:
    numero: int
    enunciado: str
    alternativas: dict[str, str] = field(default_factory=dict)
    texto_apoio: str | None = None
    secao: str | None = None
    pagina: int | None = None
    problemas: list[str] = field(default_factory=list)


def extrair_texto_pdf(caminho: Path) -> str:
    """Texto do PDF com marcadores de página. Usa pypdf; cai para pdftotext se existir."""
    try:
        from pypdf import PdfReader  # type: ignore

        leitor = PdfReader(str(caminho))
        partes = [f"=====PAGINA {i}=====\n{(p.extract_text() or '')}" for i, p in enumerate(leitor.pages, 1)]
        return "\n".join(partes)
    except ImportError:
        import shutil
        import subprocess

        if not shutil.which("pdftotext"):
            raise RuntimeError("Instale pypdf (pip install pypdf) para importar PDFs.") from None
        bruto = subprocess.run(["pdftotext", "-layout", str(caminho), "-"], capture_output=True, text=True, check=True).stdout
        return "\n".join(f"=====PAGINA {i}=====\n{t}" for i, t in enumerate(bruto.split("\f"), 1))


MARCA_DAGUA = re.compile(r"^\s*R\s*A\s*S\s*C\s*U\s*N\s*H\s*O\s*", re.I)


def _limpar_linha(l: str) -> str:
    # Provas de reaplicação trazem a marca d'água "RASCUNHO" colada ao início de algumas linhas.
    l = MARCA_DAGUA.sub("", l)
    return l.replace("�", "").replace("\t", " ").rstrip()


def _juntar(linhas: list[str]) -> str:
    """Une linhas de um bloco corrigindo hifenização de fim de linha.

    'pou-' + 'pança' -> 'pouança' (a hifenização da gráfica é removida). 'norma-' + '-padrão' (hífen repetido na
    quebra) mantém um único hífen, pois o hífen é da palavra.
    """
    saida = ""
    for l in linhas:
        l = l.strip()
        if not l:
            continue
        if not saida:
            saida = l
        elif saida.endswith("-") and l.startswith("-"):
            saida = saida + l[1:]
        elif saida.endswith("-") and l[:1].islower():
            saida = saida[:-1] + l
        else:
            saida += " " + l
    return re.sub(r"\s+", " ", saida).strip()


def parse_prova(texto: str) -> list[QuestaoImportada]:
    pagina = 0
    secao: str | None = None
    texto_atual: list[str] = []
    faixa_texto: tuple[int, int] | None = None
    base_por_numero: dict[int, str] = {}
    questoes: list[QuestaoImportada] = []
    atual: QuestaoImportada | None = None
    buffer: list[str] = []          # linhas do enunciado/alternativa em construção
    alt_atual: str | None = None
    alt_buf: list[str] = []
    capturando_texto = False
    vistos: set[int] = set()
    inicios: dict[int, str] = {}
    aguardando_inicio: str | None = None

    def fechar_alternativa() -> None:
        nonlocal alt_atual, alt_buf
        if atual is not None and alt_atual is not None:
            atual.alternativas[alt_atual] = _juntar(alt_buf)
        alt_atual, alt_buf = None, []

    def fechar_questao() -> None:
        nonlocal atual, buffer
        if atual is None:
            return
        fechar_alternativa()
        atual.enunciado = _juntar(buffer)
        if set(atual.alternativas) != set("ABCDE"):
            atual.problemas.append(f"alternativas encontradas: {''.join(sorted(atual.alternativas)) or 'nenhuma'}")
        if len(atual.enunciado) < 10:
            atual.problemas.append("enunciado muito curto")
        questoes.append(atual)
        atual, buffer = None, []

    def fechar_texto() -> None:
        nonlocal texto_atual, capturando_texto, faixa_texto
        if capturando_texto and faixa_texto:
            corpo = _juntar(texto_atual)
            for n in range(faixa_texto[0], faixa_texto[1] + 1):
                base_por_numero[n] = corpo
        texto_atual, capturando_texto = [], False

    for bruta in texto.splitlines():
        linha = _limpar_linha(bruta)
        m = MARCA_PAGINA.match(linha.strip())
        if m:
            pagina = int(m.group(1))
            continue
        s = linha.strip()
        if not s or CABECALHO.match(s) or CONFIDENCIAL.match(s) or NUM_PAGINA.match(s):
            # número de página sozinho; mas dentro de enunciado números curtos podem existir -> só descarta
            # quando a linha é APENAS dígitos (nunca é parte de alternativa, que começa com "(").
            continue

        titulo = SECOES.get(_norm(s))
        if titulo and len(s) < 40:
            fechar_questao()
            fechar_texto()
            secao = titulo
            aguardando_inicio = titulo
            continue

        mq = INICIO_QUESTAO.match(s)
        if mq and int(mq.group(1)) not in vistos and 1 <= int(mq.group(1)) <= 100 and (len(mq.group(1)) == 2 or not mq.group(1).startswith("0")):
            fechar_questao()
            fechar_texto()
            numero = int(mq.group(1))
            vistos.add(numero)
            if aguardando_inicio:
                inicios[numero] = aguardando_inicio
                aguardando_inicio = None
            atual = QuestaoImportada(numero=numero, enunciado="", secao=secao, pagina=pagina,
                                     texto_apoio=base_por_numero.get(numero))
            buffer = [mq.group(2)]
            continue

        mt = TEXTO_BASE.match(s) or TEXTO_BASE_SIMPLES.search(s)
        if mt and s.lower().startswith(("leia", "para as", "para a ", "considere")) or (mt and s.endswith(":")):
            fechar_questao()
            fechar_texto()
            faixa_texto = (int(mt.group(1)), int(mt.group(2)))
            capturando_texto = True
            texto_atual = []
            continue

        if capturando_texto:
            texto_atual.append(s)
            continue

        if atual is None:
            continue

        ma = ALTERNATIVA.match(s)
        if ma:
            fechar_alternativa()
            alt_atual = ma.group(1)
            alt_buf = [ma.group(2)]
        elif alt_atual is not None:
            alt_buf.append(s)
        else:
            buffer.append(s)

    fechar_questao()
    fechar_texto()
    # A extração do PDF pode embaralhar a ordem das páginas/colunas; por isso a disciplina vem das faixas de
    # numeração (primeira questão após cada título), não da posição da linha.
    marcos = sorted(inicios.items())
    for q in questoes:
        q.secao = None
        for n, sec in marcos:
            if n <= q.numero:
                q.secao = sec
    # texto-base capturado depois do início da questão (raro): reaplica
    for q in questoes:
        if q.texto_apoio is None and q.numero in base_por_numero:
            q.texto_apoio = base_por_numero[q.numero]
    return questoes


def sha256_arquivo(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def gravar_prova(
    conn: sqlite3.Connection,
    questoes: list[QuestaoImportada],
    *,
    titulo: str,
    sha256: str,
    ano: int | None = None,
    nome_arquivo: str | None = None,
    now=None,
) -> dict:
    """Grava documento + questões. Idempotente por sha256 (reimportar o mesmo PDF não duplica)."""
    existente = conn.execute("SELECT id FROM documentos WHERE sha256 = ?", (sha256,)).fetchone()
    if existente:
        n = conn.execute("SELECT COUNT(*) FROM questoes WHERE documento_id = ?", (existente["id"],)).fetchone()[0]
        return {"documento_id": existente["id"], "questoes": n, "ja_importado": True, "para_revisao": 0}

    agora = to_iso(now or utcnow())
    cur = conn.execute(
        "INSERT INTO documentos (nome_arquivo, tipo, banca, ano, sha256, importado_em) VALUES (?,?,?,?,?,?)",
        (nome_arquivo or titulo, "prova", "VUNESP", ano, sha256, agora),
    )
    doc_id = cur.lastrowid

    disc = {r["codigo"]: r["id"] for r in conn.execute("SELECT id, codigo FROM disciplinas")}
    revisao = 0
    for q in questoes:
        motivos = ["gabarito oficial ainda não aplicado"] + q.problemas
        cq = conn.execute(
            """INSERT INTO questoes (origem, banca, ano, documento_id, pagina_origem, numero_original, disciplina_id,
                   texto_apoio, enunciado, gabarito, precisa_revisao_manual, motivo_revisao, criada_em)
               VALUES ('oficial','VUNESP',?,?,?,?,?,?,?,NULL,1,?,?)""",
            (ano, doc_id, q.pagina, q.numero, disc.get(q.secao), q.texto_apoio, q.enunciado, "; ".join(motivos), agora),
        )
        for letra, txt in q.alternativas.items():
            conn.execute("INSERT INTO alternativas (questao_id, letra, texto) VALUES (?,?,?)", (cq.lastrowid, letra, txt))
        if q.problemas:
            revisao += 1
    return {"documento_id": doc_id, "questoes": len(questoes), "ja_importado": False, "para_revisao": revisao}


