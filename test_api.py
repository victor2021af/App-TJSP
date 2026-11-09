"""Testes de ponta a ponta da API. Exigem fastapi e httpx (requirements-dev.txt);
sem eles, são ignorados automaticamente."""
import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from app import config  # noqa: E402


def _montar(tmp_path, monkeypatch, auth_ligada):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "api.db")
    monkeypatch.setattr(config, "BACKUP_DIR", tmp_path / "backups")
    monkeypatch.setattr(config, "AUTH_ENABLED", auth_ligada)
    from app.main import app
    # base_url "localhost": o TestClient usaria "testserver", que a validação de Host recusa.
    return TestClient(app, base_url="http://localhost")


@pytest.fixture
def client(tmp_path, monkeypatch):
    """API com login LIGADO (TJSP_AUTH=on)."""
    with _montar(tmp_path, monkeypatch, True) as c:     # `with` executa o lifespan (migrações + seed)
        yield c


@pytest.fixture
def client_sem_login(tmp_path, monkeypatch):
    """API no modo padrão: login DESLIGADO."""
    with _montar(tmp_path, monkeypatch, False) as c:
        yield c


def _login(client):
    r = client.post("/api/auth/configurar", json={"nome": "Victor", "senha": "senha-forte-123"})
    assert r.status_code == 201
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_saude_e_estado_sao_publicos(client):
    assert client.get("/api/saude").json()["status"] == "ok"
    assert client.get("/api/auth/estado").json() == {"configurado": False}


@pytest.mark.parametrize("caminho", ["/api/painel", "/api/conteudo", "/api/estudo/sessao-ativa",
                                     "/api/configuracoes", "/api/backups", "/api/rede"])
def test_rotas_protegidas_exigem_login(client, caminho):
    assert client.get(caminho).status_code == 401
    assert client.get(caminho, headers={"Authorization": "Bearer falso"}).status_code == 401


def test_configurar_so_funciona_uma_vez(client):
    _login(client)
    r = client.post("/api/auth/configurar", json={"nome": "X", "senha": "outra-senha-123"})
    assert r.status_code == 409


def test_login_errado_e_bloqueio_apos_varias_falhas(client):
    _login(client)
    codigos = [client.post("/api/auth/entrar", json={"nome": "Victor", "senha": "errada"}).status_code
               for _ in range(6)]
    assert codigos[:5] == [401] * 5 and codigos[5] == 429


def test_fluxo_de_estudo_completo(client):
    h = _login(client)
    arvore = client.get("/api/conteudo", headers=h).json()
    assert [b["codigo"] for b in arvore] == ["I", "II", "III"]
    disc = arvore[0]["disciplinas"][0]["id"]
    assunto = client.get(f"/api/disciplinas/{disc}/assuntos", headers=h).json()[0]["id"]

    s = client.post("/api/estudo/sessoes", json={"assunto_id": assunto, "objetivo": "Crase"}, headers=h)
    assert s.status_code == 201 and s.json()["cronometro_correndo"] is True
    sid = s.json()["id"]
    assert client.post("/api/estudo/sessoes", json={}, headers=h).status_code == 409
    assert client.get("/api/estudo/sessao-ativa", headers=h).json()["id"] == sid
    assert client.post(f"/api/estudo/sessoes/{sid}/pausar", json={}, headers=h).json()["status"] == "pausada"
    assert client.post(f"/api/estudo/sessoes/{sid}/retomar", json={}, headers=h).json()["status"] == "em_andamento"
    fim = client.post(f"/api/estudo/sessoes/{sid}/finalizar", json={"objetivo_cumprido": True}, headers=h)
    assert fim.json()["status"] == "concluida"
    assert client.get("/api/estudo/sessao-ativa", headers=h).json() is None

    p = client.get("/api/painel", headers=h).json()
    assert p["questoes"]["acerto_pct"] is None and p["conteudo"]["por_status"]["em_andamento"] == 1


def test_status_invalido_retorna_422(client):
    h = _login(client)
    r = client.put("/api/assuntos/1/status", json={"status": "quase"}, headers=h)
    assert r.status_code == 422


def test_backup_criar_listar_restaurar(client):
    h = _login(client)
    nome = client.post("/api/backups", json={}, headers=h).json()["nome"]
    assert nome in [b["nome"] for b in client.get("/api/backups", headers=h).json()]
    assert client.post(f"/api/backups/{nome}/restaurar", json={}, headers=h).status_code == 422  # sem confirmar
    assert client.post("/api/backups/..%2Fx/restaurar", json={"confirmar": True}, headers=h).status_code in (404, 422)


# ---- modo padrão: sem login --------------------------------------------------------------------

def test_sem_login_as_rotas_funcionam_direto(client_sem_login):
    c = client_sem_login
    assert c.get("/api/auth/estado").json()["auth_ativa"] is False
    assert c.get("/api/painel").status_code == 200
    assert c.get("/api/conteudo").status_code == 200
    assert c.post("/api/estudo/sessoes", json={"objetivo": "teste"}).status_code == 201
    assert c.get("/api/estudo/sessao-ativa").json()["objetivo"] == "teste"
    assert c.post("/api/backups", json={}).status_code == 201


def test_com_login_ligado_o_estado_informa_auth_ativa(client):
    assert client.get("/api/auth/estado").json()["auth_ativa"] is True


def test_host_de_site_externo_e_recusado_mesmo_sem_login(client_sem_login):
    r = client_sem_login.get("/api/painel", headers={"Host": "evil.com"})
    assert r.status_code == 400


def test_post_sem_json_e_recusado_mesmo_sem_login(client_sem_login):
    r = client_sem_login.post("/api/backups", content=b"x", headers={"Content-Type": "text/plain"})
    assert r.status_code == 415
