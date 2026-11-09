"""Autenticação de usuário único com sessões em banco.

- Senha: scrypt (biblioteca padrão) com sal aleatório.
- Token de sessão: aleatório, enviado ao cliente uma única vez; no banco fica só o SHA-256.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sqlite3
import time
from datetime import datetime, timedelta

from .. import config
from ..db import from_iso, to_iso, utcnow
from ..errors import Conflito, Invalido, MuitasTentativas, NaoAutenticado

_N, _R, _P = 2**14, 8, 1
SENHA_MINIMA = 8


def hash_senha(senha: str) -> str:
    sal = os.urandom(16)
    dk = hashlib.scrypt(senha.encode(), salt=sal, n=_N, r=_R, p=_P, dklen=32)
    return f"scrypt${_N}${_R}${_P}${sal.hex()}${dk.hex()}"


def verificar_senha(senha: str, armazenado: str) -> bool:
    try:
        _, n, r, p, sal_hex, dk_hex = armazenado.split("$")
        dk = hashlib.scrypt(senha.encode(), salt=bytes.fromhex(sal_hex),
                            n=int(n), r=int(r), p=int(p), dklen=32)
        return hmac.compare_digest(dk, bytes.fromhex(dk_hex))
    except (ValueError, TypeError):
        return False


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def configurado(conn: sqlite3.Connection) -> bool:
    return conn.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0] > 0


def criar_usuario(conn: sqlite3.Connection, nome: str, senha: str) -> int:
    """Cria o único usuário. Só funciona no primeiro acesso."""
    nome = nome.strip()
    if not nome:
        raise Invalido("Informe um nome.")
    if len(senha) < SENHA_MINIMA:
        raise Invalido(f"A senha deve ter pelo menos {SENHA_MINIMA} caracteres.")
    if configurado(conn):
        raise Conflito("O aplicativo já foi configurado.")
    cur = conn.execute(
        "INSERT INTO usuarios (nome, senha_hash, criado_em) VALUES (?,?,?)",
        (nome, hash_senha(senha), to_iso(utcnow())),
    )
    conn.commit()
    return cur.lastrowid


def entrar(conn: sqlite3.Connection, nome: str, senha: str, now: datetime | None = None) -> str:
    now = now or utcnow()
    linha = conn.execute("SELECT id, senha_hash FROM usuarios WHERE nome = ?", (nome.strip(),)).fetchone()
    # Verifica sempre um hash, para não revelar por tempo se o usuário existe.
    armazenado = linha["senha_hash"] if linha else hash_senha("senha-descartavel")
    ok = verificar_senha(senha, armazenado)
    if not (linha and ok):
        raise NaoAutenticado("Nome ou senha incorretos.")
    token = secrets.token_urlsafe(32)
    conn.execute("DELETE FROM sessoes_login WHERE expira_em < ?", (to_iso(now),))
    conn.execute(
        "INSERT INTO sessoes_login (usuario_id, token_hash, criado_em, expira_em) VALUES (?,?,?,?)",
        (linha["id"], _hash_token(token), to_iso(now), to_iso(now + timedelta(days=config.SESSION_DAYS))),
    )
    conn.commit()
    return token


def usuario_do_token(conn: sqlite3.Connection, token: str | None, now: datetime | None = None) -> sqlite3.Row:
    now = now or utcnow()
    if not token:
        raise NaoAutenticado("Autenticação necessária.")
    linha = conn.execute(
        "SELECT u.id, u.nome, s.expira_em FROM sessoes_login s JOIN usuarios u ON u.id = s.usuario_id"
        " WHERE s.token_hash = ?",
        (_hash_token(token),),
    ).fetchone()
    if not linha or from_iso(linha["expira_em"]) < now:
        raise NaoAutenticado("Sessão inválida ou expirada.")
    return linha


def sair(conn: sqlite3.Connection, token: str | None) -> None:
    if token:
        conn.execute("DELETE FROM sessoes_login WHERE token_hash = ?", (_hash_token(token),))
        conn.commit()


class LimitadorDeLogin:
    """Bloqueio simples em memória: `maximo` falhas por chave dentro de `janela_seg`."""

    def __init__(self, maximo: int = 5, janela_seg: int = 300, relogio=time.monotonic):
        self.maximo, self.janela, self._rel = maximo, janela_seg, relogio
        self._falhas: dict[str, list[float]] = {}

    def _limpar(self, chave: str) -> list[float]:
        agora = self._rel()
        recentes = [t for t in self._falhas.get(chave, []) if agora - t < self.janela]
        self._falhas[chave] = recentes
        return recentes

    def verificar(self, chave: str) -> None:
        if len(self._limpar(chave)) >= self.maximo:
            raise MuitasTentativas("Muitas tentativas de login. Aguarde alguns minutos.")

    def registrar_falha(self, chave: str) -> None:
        self._limpar(chave).append(self._rel())

    def limpar(self, chave: str) -> None:
        self._falhas.pop(chave, None)
