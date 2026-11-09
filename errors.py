"""Exceções de domínio. Os routers as convertem em respostas HTTP."""


class ErroDeDominio(Exception):
    status_http = 400

    def __init__(self, mensagem: str):
        super().__init__(mensagem)
        self.mensagem = mensagem


class NaoEncontrado(ErroDeDominio):
    status_http = 404


class Conflito(ErroDeDominio):
    status_http = 409


class Invalido(ErroDeDominio):
    status_http = 422


class NaoAutenticado(ErroDeDominio):
    status_http = 401


class MuitasTentativas(ErroDeDominio):
    status_http = 429
