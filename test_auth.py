from datetime import timedelta

import pytest

from app.errors import Conflito, Invalido, MuitasTentativas, NaoAutenticado
from app.services import auth
from conftest import utc

T0 = utc(2026, 11, 8, 12, 0, 0)


def test_primeiro_acesso_cria_usuario_e_so_uma_vez(conn):
    assert not auth.configurado(conn)
    auth.criar_usuario(conn, "Victor", "senha-forte-123")
    assert auth.configurado(conn)
    with pytest.raises(Conflito):
        auth.criar_usuario(conn, "Outro", "senha-forte-123")


def test_validacao_de_entrada(conn):
    with pytest.raises(Invalido):
        auth.criar_usuario(conn, "  ", "senha-forte-123")
    with pytest.raises(Invalido):
        auth.criar_usuario(conn, "Victor", "curta")


def test_senha_nao_fica_em_texto_e_token_so_como_hash(conn):
    auth.criar_usuario(conn, "Victor", "senha-forte-123")
    h = conn.execute("SELECT senha_hash FROM usuarios").fetchone()[0]
    assert "senha-forte-123" not in h and h.startswith("scrypt$")
    token = auth.entrar(conn, "Victor", "senha-forte-123", now=T0)
    guardado = conn.execute("SELECT token_hash FROM sessoes_login").fetchone()[0]
    assert token not in guardado and len(guardado) == 64


def test_login_correto_e_incorreto(conn):
    auth.criar_usuario(conn, "Victor", "senha-forte-123")
    token = auth.entrar(conn, "Victor", "senha-forte-123", now=T0)
    assert auth.usuario_do_token(conn, token, now=T0)["nome"] == "Victor"
    for nome, senha in (("Victor", "errada-errada"), ("Fulano", "senha-forte-123")):
        with pytest.raises(NaoAutenticado):
            auth.entrar(conn, nome, senha, now=T0)


def test_token_expira_e_logout_invalida(conn):
    auth.criar_usuario(conn, "Victor", "senha-forte-123")
    token = auth.entrar(conn, "Victor", "senha-forte-123", now=T0)
    with pytest.raises(NaoAutenticado):
        auth.usuario_do_token(conn, token, now=T0 + timedelta(days=31))
    with pytest.raises(NaoAutenticado):
        auth.usuario_do_token(conn, None)
    with pytest.raises(NaoAutenticado):
        auth.usuario_do_token(conn, "token-inventado", now=T0)
    auth.sair(conn, token)
    with pytest.raises(NaoAutenticado):
        auth.usuario_do_token(conn, token, now=T0)


def test_limitador_bloqueia_apos_falhas_e_libera_com_o_tempo():
    t = [0.0]
    lim = auth.LimitadorDeLogin(maximo=3, janela_seg=60, relogio=lambda: t[0])
    for _ in range(3):
        lim.verificar("ip")
        lim.registrar_falha("ip")
    with pytest.raises(MuitasTentativas):
        lim.verificar("ip")
    lim.verificar("outro-ip")         # outra origem não é afetada
    t[0] = 61
    lim.verificar("ip")               # janela passou
