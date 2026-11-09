import pytest

from app.errors import Invalido
from app.services import fontes_web as fw

OK = lambda h: True  # noqa: E731


def test_aceita_dominio_oficial_e_subdominio():
    assert fw.validar_url("https://www.tjsp.jus.br/a.pdf", resolver=OK).startswith("https://www.tjsp.jus.br")
    assert fw.validar_url("https://dje.tjsp.jus.br/x", resolver=OK)


@pytest.mark.parametrize("url", [
    "http://www.tjsp.jus.br/a.pdf",                 # sem https
    "https://tjsp.jus.br.evil.com/a.pdf",           # sufixo enganoso
    "https://evil.com/tjsp.jus.br",                 # domínio no caminho
    "https://user:pw@www.tjsp.jus.br/a.pdf",        # credenciais
    "https://nottjsp.jus.br/a.pdf",                 # termina igual, mas não é subdomínio
    "file:///etc/passwd", "", "https://127.0.0.1/a.pdf",
])
def test_rejeita_urls_perigosas(url):
    with pytest.raises(Invalido):
        fw.validar_url(url, resolver=OK)


def test_rejeita_host_que_resolve_para_rede_privada():
    with pytest.raises(Invalido):
        fw.validar_url("https://www.tjsp.jus.br/a.pdf", resolver=lambda h: False)


def test_dominios_extras_por_ambiente(monkeypatch):
    monkeypatch.setenv("TJSP_FONTES_PERMITIDAS", "exemplo.org")
    assert fw.validar_url("https://exemplo.org/p.pdf", resolver=OK)


def test_busca_desligada_sem_chave(monkeypatch):
    monkeypatch.delenv("GOOGLE_CSE_KEY", raising=False)
    with pytest.raises(Exception, match="desligada"):
        fw.buscar("gabarito tjsp")
