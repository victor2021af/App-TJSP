"""Backup e restauração do banco SQLite.

Usa a API de backup do próprio SQLite, que gera uma cópia consistente mesmo com o
aplicativo em uso (a cópia simples do arquivo pode sair corrompida no modo WAL).
"""
from __future__ import annotations

import re
import sqlite3
from datetime import datetime
from pathlib import Path

from .. import config
from ..db import connect, utcnow
from ..errors import Invalido, NaoEncontrado
from ..migrate import apply_migrations

_NOME_VALIDO = re.compile(r"^(tjsp|pre-restauracao)-\d{8}-\d{6}(-\d+)?\.db$")
TABELAS_ESSENCIAIS = {"schema_migrations", "usuarios", "blocos", "assuntos", "sessoes_estudo"}


def _caminho_livre(pasta: Path, prefixo: str, now: datetime) -> Path:
    base = f"{prefixo}-{now.strftime('%Y%m%d-%H%M%S')}"
    destino = pasta / f"{base}.db"
    i = 1
    while destino.exists():
        destino = pasta / f"{base}-{i}.db"
        i += 1
    return destino


def _copiar(origem: sqlite3.Connection, destino: sqlite3.Connection) -> None:
    origem.backup(destino)


def criar_backup(db_path: Path | None = None, backup_dir: Path | None = None,
                 prefixo: str = "tjsp", now: datetime | None = None) -> Path:
    db_path = db_path or config.DB_PATH
    backup_dir = backup_dir or config.BACKUP_DIR
    backup_dir.mkdir(parents=True, exist_ok=True)
    destino = _caminho_livre(backup_dir, prefixo, now or utcnow())
    origem = connect(db_path)
    saida = sqlite3.connect(destino)
    try:
        _copiar(origem, saida)
    finally:
        saida.close()
        origem.close()
    return destino


def listar(backup_dir: Path | None = None) -> list[dict]:
    backup_dir = backup_dir or config.BACKUP_DIR
    if not backup_dir.exists():
        return []
    itens = []
    for p in sorted(backup_dir.glob("*.db"), reverse=True):
        if _NOME_VALIDO.match(p.name):
            st = p.stat()
            itens.append({"nome": p.name, "bytes": st.st_size,
                          "automatico_de_seguranca": p.name.startswith("pre-restauracao")})
    return itens


def podar(backup_dir: Path | None = None, manter: int | None = None) -> int:
    """Mantém os `manter` backups regulares mais recentes. Backups de pré-restauração nunca são apagados."""
    backup_dir = backup_dir or config.BACKUP_DIR
    manter = config.BACKUP_RETENTION if manter is None else manter
    regulares = sorted((p for p in backup_dir.glob("tjsp-*.db") if _NOME_VALIDO.match(p.name)), reverse=True)
    removidos = 0
    for p in regulares[manter:]:
        p.unlink()
        removidos += 1
    return removidos


def backup_automatico_se_necessario(db_path: Path | None = None, backup_dir: Path | None = None,
                                    horas: int | None = None, now: datetime | None = None) -> Path | None:
    """Cria um backup se o mais recente tiver mais de `horas` horas (ou se não houver nenhum)."""
    backup_dir = backup_dir or config.BACKUP_DIR
    horas = config.AUTO_BACKUP_HOURS if horas is None else horas
    now = now or utcnow()
    existentes = sorted(backup_dir.glob("tjsp-*.db")) if backup_dir.exists() else []
    if existentes:
        idade_h = (now.timestamp() - existentes[-1].stat().st_mtime) / 3600
        if idade_h < horas:
            return None
    novo = criar_backup(db_path, backup_dir, "tjsp", now)
    podar(backup_dir)
    return novo


def _validar(arquivo: Path) -> None:
    try:
        con = sqlite3.connect(f"file:{arquivo}?mode=ro", uri=True)
    except sqlite3.Error as e:
        raise Invalido(f"Não foi possível abrir o backup: {e}")
    try:
        if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise Invalido("O backup não passou na verificação de integridade.")
        tabelas = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        faltando = TABELAS_ESSENCIAIS - tabelas
        if faltando:
            raise Invalido(f"O arquivo não parece um backup do TJSP Aprovação (faltam tabelas: {sorted(faltando)}).")
    except sqlite3.DatabaseError as e:
        raise Invalido(f"Arquivo inválido: {e}")
    finally:
        con.close()


def restaurar(nome: str, db_path: Path | None = None, backup_dir: Path | None = None,
              now: datetime | None = None) -> dict:
    """Restaura um backup. Antes, salva o estado atual como `pre-restauracao-*` para permitir desfazer."""
    db_path = db_path or config.DB_PATH
    backup_dir = backup_dir or config.BACKUP_DIR
    if not _NOME_VALIDO.match(nome):  # bloqueia caminhos e nomes arbitrários
        raise Invalido("Nome de backup inválido.")
    arquivo = backup_dir / nome
    if not arquivo.is_file():
        raise NaoEncontrado("Backup não encontrado.")
    _validar(arquivo)

    seguranca = criar_backup(db_path, backup_dir, "pre-restauracao", now)

    origem = sqlite3.connect(f"file:{arquivo}?mode=ro", uri=True)
    vivo = connect(db_path)
    try:
        origem.backup(vivo)  # sobrescreve o conteúdo do banco em uso, de forma atômica
        vivo.commit()
        aplicadas = apply_migrations(vivo)  # se o backup for de uma versão mais antiga do esquema
    finally:
        origem.close()
        vivo.close()
    return {"restaurado": nome, "backup_de_seguranca": seguranca.name, "migracoes_aplicadas": aplicadas}
