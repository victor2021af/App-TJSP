import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import db as dbmod  # noqa: E402
from app.migrate import apply_migrations  # noqa: E402
from app.services.seed import carregar_edital  # noqa: E402


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "teste.db"


@pytest.fixture
def conn(db_path):
    c = dbmod.connect(db_path)
    apply_migrations(c)
    carregar_edital(c)
    yield c
    c.close()


def utc(*args):
    return datetime(*args, tzinfo=timezone.utc)
