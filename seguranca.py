"""Proteções que valem mesmo com o login desligado.

1. Cabeçalho Host: só localhost, endereços de rede privada (192.168.x.x, 10.x.x.x, 172.16-31.x.x)
   e nomes explicitamente liberados. Isso bloqueia "DNS rebinding": um site malicioso apontando
   seu domínio para 127.0.0.1 para ler o app pelo seu navegador.
2. Requisições que alteram dados precisam ser application/json. Um site qualquer não consegue
   enviar esse tipo entre origens sem pedir permissão (preflight de CORS, que o app nega), o que
   barra pedidos forjados (CSRF) vindos de outras páginas abertas no navegador.
"""
from __future__ import annotations

import ipaddress

METODOS_QUE_ALTERAM = {"POST", "PUT", "PATCH", "DELETE"}


def _so_host(valor: str) -> str:
    valor = valor.strip().lower()
    if valor.startswith("["):  # IPv6 literal: [::1]:8443
        return valor[1:valor.index("]")] if "]" in valor else valor
    return valor.rsplit(":", 1)[0] if valor.count(":") == 1 else valor


def host_permitido(cabecalho_host: str | None, extras: set[str] | frozenset[str] = frozenset()) -> bool:
    if not cabecalho_host:
        return False
    try:
        host = _so_host(cabecalho_host)
    except ValueError:
        return False
    if host == "localhost" or host in extras:
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_loopback or (ip.is_private and not ip.is_unspecified)


def corpo_json_valido(metodo: str, content_type: str | None) -> bool:
    if metodo.upper() not in METODOS_QUE_ALTERAM:
        return True
    return (content_type or "").split(";")[0].strip().lower() == "application/json"
