"""Ponto de entrada da API. Execute com: uvicorn app.main:app"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .db import connect
from .errors import ErroDeDominio
from .seguranca import corpo_json_valido, host_permitido
from .migrate import apply_migrations
from .routers import auth, backups, banco, conteudo, estudo, painel, saude
from .routers import ia as ia_router
from .services import backup as backup_service
from .services.seed import carregar_edital

log = logging.getLogger("tjsp")


@asynccontextmanager
async def lifespan(app: FastAPI):
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = connect()
    try:
        aplicadas = apply_migrations(conn)
        novos = carregar_edital(conn)
    finally:
        conn.close()
    if aplicadas:
        log.info("Migrações aplicadas: %s", aplicadas)
    if any(novos.values()):
        log.info("Edital carregado: %s", novos)
    try:
        criado = backup_service.backup_automatico_se_necessario()
        if criado:
            log.info("Backup automático criado: %s", criado.name)
    except Exception:  # backup nunca deve impedir o app de abrir
        log.exception("Falha no backup automático")
    yield


app = FastAPI(title="TJSP Aprovação", version=config.APP_VERSION, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def cabecalhos_de_seguranca(request: Request, call_next):
    if not host_permitido(request.headers.get("host"), config.ALLOWED_HOSTS):
        return JSONResponse({"detalhe": "Host não permitido."}, status_code=400)
    if not corpo_json_valido(request.method, request.headers.get("content-type")):
        return JSONResponse({"detalhe": "Use Content-Type: application/json."}, status_code=415)
    resposta = await call_next(request)
    resposta.headers.setdefault("X-Content-Type-Options", "nosniff")
    resposta.headers.setdefault("X-Frame-Options", "DENY")
    resposta.headers.setdefault("Referrer-Policy", "same-origin")
    resposta.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; "
        "script-src 'self'; connect-src 'self'; frame-ancestors 'none'",
    )
    return resposta


@app.exception_handler(ErroDeDominio)
async def erro_de_dominio(_: Request, exc: ErroDeDominio):
    return JSONResponse({"detalhe": exc.mensagem}, status_code=exc.status_http)


for r in (saude.router, auth.router, conteudo.router, estudo.router, painel.router, backups.router, banco.router, ia_router.router):
    app.include_router(r)

# Frontend compilado, servido na mesma origem da API (necessário para HTTPS/PWA simples).
_dist = config.FRONTEND_DIST
if _dist.is_dir() and (_dist / "index.html").is_file():
    if (_dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=_dist / "assets"), name="assets")

    @app.get("/{caminho:path}", include_in_schema=False)
    def frontend(caminho: str):
        if caminho.startswith("api/"):
            raise HTTPException(status_code=404)
        raiz = _dist.resolve()
        arquivo = (raiz / caminho).resolve()
        if caminho and arquivo.is_file() and raiz in arquivo.parents:
            alvo = arquivo
        else:
            alvo = raiz / "index.html"
        # O service worker e o HTML nunca podem ficar presos em cache, senão o app não atualiza.
        sem_cache = alvo.name in ("sw.js", "index.html")
        return FileResponse(alvo, headers={"Cache-Control": "no-cache"} if sem_cache else None)
