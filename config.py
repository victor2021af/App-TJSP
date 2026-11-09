"""Configuração central. Tudo pode ser sobrescrito por variáveis de ambiente."""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BASE_DIR.parent

# Dados do usuário (banco, backups, uploads) ficam fora do código e fora do navegador.
DATA_DIR = Path(os.environ.get("TJSP_DATA_DIR", BASE_DIR / "data")).resolve()
DB_PATH = DATA_DIR / "tjsp.db"
BACKUP_DIR = DATA_DIR / "backups"
UPLOAD_DIR = DATA_DIR / "uploads"

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
SEED_DIR = Path(__file__).resolve().parent / "seed"

# Frontend compilado (frontend/dist). Se existir, o backend o serve na mesma origem,
# o que simplifica HTTPS e a instalação do PWA.
FRONTEND_DIST = Path(os.environ.get("TJSP_FRONTEND_DIST", PROJECT_DIR / "frontend" / "dist"))

APP_VERSION = "0.1.0"
DEFAULT_TIMEZONE = os.environ.get("TJSP_TZ", "America/Sao_Paulo")

# Origens extras permitidas no CORS (apenas necessário no modo de desenvolvimento do Vite).
CORS_ORIGINS = [
    o.strip()
    for o in os.environ.get(
        "TJSP_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if o.strip()
]

# Login: DESLIGADO por padrão (uso pessoal local). Para religar: defina TJSP_AUTH=on antes de iniciar.
AUTH_ENABLED = os.environ.get("TJSP_AUTH", "off").strip().lower() in ("on", "1", "true", "sim")

# Nomes de host extras aceitos (além de localhost e IPs de rede privada). Separe por vírgula.
ALLOWED_HOSTS = {
    h.strip().lower() for h in os.environ.get("TJSP_ALLOWED_HOSTS", "").split(",") if h.strip()
}

SESSION_DAYS = int(os.environ.get("TJSP_SESSION_DAYS", "30"))
BACKUP_RETENTION = int(os.environ.get("TJSP_BACKUP_RETENTION", "30"))
AUTO_BACKUP_HOURS = int(os.environ.get("TJSP_AUTO_BACKUP_HOURS", "24"))
