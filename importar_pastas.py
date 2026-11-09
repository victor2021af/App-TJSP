"""Importa provas e gabaritos de uma pasta.  Uso:  python -m app.importar_pastas <pasta>

- PDFs com 'prova' no nome -> questões (100 por prova antiga), sem gabarito.
- PDFs com 'gabarito' no nome -> gabaritos guardados SEM vínculo (um por versão).
- Único vínculo automático: gabarito e prova de 02.07.2023, cujo pareamento foi conferido recalculando 4 questões
  de Matemática (71-E, 72-A, 74-D, 75-B). Todos os demais exigem conferência sua (ver README).
Gabaritos em imagem (digitalizados) não têm texto e são listados como 'precisa leitura manual'.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from . import config
from .db import connect
from .migrate import apply_migrations
from .services import gabaritos, importador
from .services.seed import carregar_edital

CONFERENCIA_0207 = ("Pareamento conferido recalculando 4 questões de Matemática da prova (71-E, 72-A, 74-D, 75-B), "
                    "todas coincidentes com o gabarito oficial de 02/07/2023 (versão 1).")


def _ano(nome: str) -> int | None:
    m = re.search(r"(20\d{2})", nome)
    return int(m.group(1)) if m else None


def executar(pasta: Path, db_path: Path | None = None) -> list[str]:
    log: list[str] = []
    conn = connect(db_path or config.DB_PATH)
    apply_migrations(conn)
    carregar_edital(conn)
    arquivos = sorted(pasta.glob("*.pdf"))
    for f in arquivos:
        n = f.name.lower()
        if "gabarito" in n:
            continue
        if "prova" not in n or "edital" in n or "tjsp26" in n:
            log.append(f"ignorado: {f.name}")
            continue
        r = importador.gravar_prova(conn, importador.parse_prova(importador.extrair_texto_pdf(f)), titulo=f.stem,
                                    sha256=importador.sha256_arquivo(f), ano=_ano(f.name), nome_arquivo=f.name)
        log.append(f"prova {f.name}: {r['questoes']} questões" + (" (já importada)" if r["ja_importado"] else ""))
        conn.commit()
    for f in arquivos:
        if "gabarito" not in f.name.lower():
            continue
        texto = importador.extrair_texto_pdf(f)
        if not re.search(r"\d{1,3}\s*[-–]\s*[A-E]", texto):
            log.append(f"gabarito {f.name}: sem texto (imagem) — precisa leitura manual")
            continue
        try:
            for g in gabaritos.armazenar(conn, texto, descricao=f.stem, origem=f.name, sha256=importador.sha256_arquivo(f)):
                log.append(f"gabarito {f.name}: versão {g['versao']} guardada (não vinculada)")
        except Exception as e:  # noqa: BLE001
            log.append(f"gabarito {f.name}: NÃO guardado — {e}")
        conn.commit()
    # vínculo conferido de 02/07/2023
    prova = conn.execute("SELECT id FROM documentos WHERE nome_arquivo LIKE '%02.07.2023%Prova%'").fetchone()
    gab = conn.execute("SELECT id FROM gabaritos WHERE origem LIKE '%02.07.2023%' AND versao='1' AND documento_id IS NULL").fetchone()
    if prova and gab:
        r = gabaritos.aplicar(conn, gab["id"], prova["id"], CONFERENCIA_0207)
        conn.commit()
        log.append(f"gabarito 02/07/2023 aplicado: {r['questoes_atualizadas']} questões")
    conn.close()
    return log


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Uso: python -m app.importar_pastas <pasta com os PDFs>")
    print("\n".join(executar(Path(sys.argv[1]))))
