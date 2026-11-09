"""Camada de IA: provedor intercambiável (Anthropic/OpenAI), chaves SÓ no backend, via stdlib (sem SDK).

Variáveis de ambiente (nunca vão ao navegador):
  TJSP_IA_PROVEDOR   anthropic | openai          (padrão: o que tiver chave)
  ANTHROPIC_API_KEY / OPENAI_API_KEY
  TJSP_IA_MODELO     nome do modelo do provedor (obrigatório: não há padrão embutido para não ficar desatualizado)
"""
from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass

from ..errors import ErroDeDominio


class IaIndisponivel(ErroDeDominio):
    status_http = 503


@dataclass
class Imagem:
    dados: bytes
    tipo_mime: str


class Provedor:
    nome = ""

    def completar(self, sistema: str, mensagens: list[dict], imagem: Imagem | None = None, max_tokens: int = 2000) -> str:
        raise NotImplementedError


def _post(url: str, cabecalhos: dict, corpo: dict, timeout: int = 120) -> dict:
    req = urllib.request.Request(url, data=json.dumps(corpo).encode(), headers={"content-type": "application/json", **cabecalhos})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 (URLs fixas dos provedores)
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise IaIndisponivel(f"O provedor de IA recusou o pedido (HTTP {e.code}). Verifique chave e modelo.") from None
    except (urllib.error.URLError, TimeoutError):
        raise IaIndisponivel("Não foi possível falar com o provedor de IA (sem internet ou tempo esgotado).") from None


class Anthropic(Provedor):
    nome = "anthropic"

    def __init__(self, chave: str, modelo: str):
        self.chave, self.modelo = chave, modelo

    def completar(self, sistema, mensagens, imagem=None, max_tokens=2000):
        msgs = [dict(m) for m in mensagens]
        if imagem:
            msgs[-1]["content"] = [
                {"type": "image", "source": {"type": "base64", "media_type": imagem.tipo_mime,
                                             "data": base64.b64encode(imagem.dados).decode()}},
                {"type": "text", "text": msgs[-1]["content"]},
            ]
        r = _post("https://api.anthropic.com/v1/messages",
                  {"x-api-key": self.chave, "anthropic-version": "2023-06-01"},
                  {"model": self.modelo, "max_tokens": max_tokens, "system": sistema, "messages": msgs})
        return "".join(b.get("text", "") for b in r.get("content", []))


class OpenAI(Provedor):
    nome = "openai"

    def __init__(self, chave: str, modelo: str):
        self.chave, self.modelo = chave, modelo

    def completar(self, sistema, mensagens, imagem=None, max_tokens=2000):
        msgs = [{"role": "system", "content": sistema}] + [dict(m) for m in mensagens]
        if imagem:
            url = f"data:{imagem.tipo_mime};base64,{base64.b64encode(imagem.dados).decode()}"
            msgs[-1]["content"] = [{"type": "text", "text": msgs[-1]["content"]},
                                   {"type": "image_url", "image_url": {"url": url}}]
        r = _post("https://api.openai.com/v1/chat/completions", {"authorization": f"Bearer {self.chave}"},
                  {"model": self.modelo, "max_completion_tokens": max_tokens, "messages": msgs})
        return r["choices"][0]["message"]["content"] or ""


_substituto: Provedor | None = None  # usado nos testes


def definir_provedor_de_teste(p: Provedor | None) -> None:
    global _substituto
    _substituto = p


def provedor_atual() -> Provedor:
    if _substituto:
        return _substituto
    modelo = os.environ.get("TJSP_IA_MODELO", "").strip()
    escolha = os.environ.get("TJSP_IA_PROVEDOR", "").strip().lower()
    ak, ok = os.environ.get("ANTHROPIC_API_KEY", ""), os.environ.get("OPENAI_API_KEY", "")
    if not escolha:
        escolha = "anthropic" if ak else "openai" if ok else ""
    if escolha not in ("anthropic", "openai") or not (ak if escolha == "anthropic" else ok) or not modelo:
        raise IaIndisponivel("IA não configurada: defina TJSP_IA_PROVEDOR, a chave do provedor e TJSP_IA_MODELO (veja docs/IA.md).")
    return Anthropic(ak, modelo) if escolha == "anthropic" else OpenAI(ok, modelo)


def estado() -> dict:
    try:
        return {"configurada": True, "provedor": provedor_atual().nome}
    except IaIndisponivel as e:
        return {"configurada": False, "provedor": None, "motivo": e.mensagem}


def extrair_json(texto: str) -> dict:
    """Pega o primeiro objeto JSON da resposta (modelos às vezes cercam com ```)."""
    ini, fim = texto.find("{"), texto.rfind("}")
    if ini < 0 or fim <= ini:
        raise IaIndisponivel("A IA não devolveu um JSON válido; tente novamente.")
    try:
        return json.loads(texto[ini:fim + 1])
    except json.JSONDecodeError:
        raise IaIndisponivel("A IA devolveu um JSON malformado; tente novamente.") from None
