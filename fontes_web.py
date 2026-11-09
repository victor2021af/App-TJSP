"""Busca e download de provas/gabaritos oficiais na web — com trava de segurança.

- Busca: API oficial do Google (Programmable Search). Exige GOOGLE_CSE_KEY e GOOGLE_CSE_CX no ambiente; sem elas a
  busca fica desligada (não há "raspagem" do site do Google, que viola os termos dele).
- Download: só HTTPS, só domínios permitidos (padrão: sites oficiais; ampliável por TJSP_FONTES_PERMITIDAS),
  sem credenciais na URL, só IPs públicos (evita SSRF contra a rede de casa), limite de 30 MB, precisa ser PDF.
- Nada é copiado de bancos comerciais de questões: sites assim ficam fora da lista por padrão (termos de uso/autoria).
"""
from __future__ import annotations

import ipaddress
import json
import os
import socket
import urllib.parse
import urllib.request

from ..errors import Invalido
from .ia import IaIndisponivel

PADRAO = ("vunesp.com.br", "tjsp.jus.br")
LIMITE = 30 * 1024 * 1024


def dominios_permitidos() -> tuple[str, ...]:
    extra = tuple(d.strip().lower() for d in os.environ.get("TJSP_FONTES_PERMITIDAS", "").split(",") if d.strip())
    return PADRAO + extra


def _host_permitido(host: str, permitidos) -> bool:
    host = host.lower().rstrip(".")
    return any(host == d or host.endswith("." + d) for d in permitidos)


def _ip_publico(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        return False
    return all(ipaddress.ip_address(i[4][0]).is_global for i in infos)


def validar_url(url: str, permitidos=None, resolver=_ip_publico) -> str:
    u = urllib.parse.urlsplit((url or "").strip())
    if u.scheme != "https" or not u.hostname:
        raise Invalido("Use um endereço https://.")
    if u.username or u.password:
        raise Invalido("Endereço com usuário/senha não é aceito.")
    if not _host_permitido(u.hostname, permitidos or dominios_permitidos()):
        raise Invalido("Domínio fora da lista permitida (" + ", ".join(permitidos or dominios_permitidos()) + ").")
    if not resolver(u.hostname):
        raise Invalido("O domínio não resolve para um endereço público.")
    return u.geturl()


class _SemRedirecionar(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):  # redirecionamento teria de ser revalidado; simplesmente recusamos
        return None


def baixar_pdf(url: str) -> bytes:
    url = validar_url(url)
    opener = urllib.request.build_opener(_SemRedirecionar)
    try:
        with opener.open(urllib.request.Request(url, headers={"User-Agent": "tjsp-aprovacao/0.1"}), timeout=60) as r:  # noqa: S310
            dados = r.read(LIMITE + 1)
    except Exception as e:  # noqa: BLE001
        raise Invalido(f"Não consegui baixar o arquivo ({type(e).__name__}). Baixe manualmente e envie o PDF.") from None
    if len(dados) > LIMITE:
        raise Invalido("Arquivo maior que 30 MB.")
    if not dados.startswith(b"%PDF"):
        raise Invalido("O endereço não devolveu um PDF.")
    return dados


def buscar(consulta: str, n: int = 8) -> list[dict]:
    chave, cx = os.environ.get("GOOGLE_CSE_KEY", ""), os.environ.get("GOOGLE_CSE_CX", "")
    if not chave or not cx:
        raise IaIndisponivel("Busca na web desligada: defina GOOGLE_CSE_KEY e GOOGLE_CSE_CX (veja docs/FONTES.md).")
    q = urllib.parse.urlencode({"key": chave, "cx": cx, "q": consulta, "num": max(1, min(n, 10))})
    try:
        with urllib.request.urlopen("https://www.googleapis.com/customsearch/v1?" + q, timeout=30) as r:  # noqa: S310
            itens = json.loads(r.read()).get("items", [])
    except Exception:  # noqa: BLE001
        raise IaIndisponivel("A busca na web falhou (chave, cota ou internet).") from None
    permit = dominios_permitidos()
    out = []
    for i in itens:
        host = urllib.parse.urlsplit(i.get("link", "")).hostname or ""
        out.append({"titulo": i.get("title"), "url": i.get("link"), "trecho": i.get("snippet"),
                    "importavel": _host_permitido(host, permit)})
    return out
