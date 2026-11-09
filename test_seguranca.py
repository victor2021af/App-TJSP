import pytest

from app.seguranca import corpo_json_valido, host_permitido


@pytest.mark.parametrize("host", [
    "localhost", "localhost:8000", "127.0.0.1:8000", "[::1]:8443", "::1",
    "192.168.0.15:8443", "10.1.2.3", "172.16.0.1:8443", "172.31.255.1",
])
def test_hosts_locais_e_de_rede_privada_sao_aceitos(host):
    assert host_permitido(host)


@pytest.mark.parametrize("host", [
    None, "", "evil.com", "evil.com:8000", "localhost.evil.com", "127.0.0.1.evil.com",
    "8.8.8.8", "172.32.0.1", "192.169.0.1", "0.0.0.0", "meu-site.com.br:8443",
])
def test_hosts_externos_ou_nomes_estranhos_sao_recusados(host):
    assert not host_permitido(host)   # protege contra DNS rebinding


def test_nomes_extras_precisam_ser_liberados_explicitamente():
    assert not host_permitido("pc-do-victor:8443")
    assert host_permitido("pc-do-victor:8443", {"pc-do-victor"})


def test_metodos_que_alteram_exigem_json():
    assert corpo_json_valido("GET", None)
    assert corpo_json_valido("POST", "application/json")
    assert corpo_json_valido("PUT", "Application/JSON; charset=utf-8")
    for tipo in (None, "", "text/plain", "application/x-www-form-urlencoded", "multipart/form-data"):
        assert not corpo_json_valido("POST", tipo)   # os tipos que um site forjaria sem preflight
        assert not corpo_json_valido("DELETE", tipo)
