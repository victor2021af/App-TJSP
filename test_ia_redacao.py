import pytest

from app import config
from app.errors import Conflito, Invalido
from app.services import gabaritos, ia, importador, professor, redacao
from tests.test_questoes_fase3 import _gab70, prova_sintetica  # noqa: F401

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 100


class Falso(ia.Provedor):
    nome = "falso"

    def __init__(self, resposta):
        self.resposta, self.chamadas = resposta, []

    def completar(self, sistema, mensagens, imagem=None, max_tokens=2000):
        self.chamadas.append((sistema, mensagens, imagem))
        return self.resposta


@pytest.fixture(autouse=True)
def limpar():
    yield
    ia.definir_provedor_de_teste(None)


@pytest.fixture
def uploads(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "UPLOAD_DIR", tmp_path / "up")


def test_ia_nao_configurada(monkeypatch):
    for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "TJSP_IA_MODELO", "TJSP_IA_PROVEDOR"):
        monkeypatch.delenv(k, raising=False)
    assert ia.estado()["configurada"] is False
    with pytest.raises(ia.IaIndisponivel):
        ia.provedor_atual()


def test_extrair_json_com_cerca():
    assert ia.extrair_json('```json\n{"a": 1}\n```') == {"a": 1}
    with pytest.raises(ia.IaIndisponivel):
        ia.extrair_json("sem json")


def test_professor_usa_contexto_real_e_guarda_historico(conn):
    f = Falso("Resposta do professor")
    ia.definir_provedor_de_teste(f)
    r = professor.conversar(conn, "Explique crase")
    assert r["gerado_por_ia"] and r["resposta"] == "Resposta do professor"
    assert "sem dados" in f.chamadas[0][0]          # sem histórico: não inventa desempenho
    professor.conversar(conn, "E agora?")
    assert len(f.chamadas[1][1]) == 3                # 2 mensagens anteriores + a nova
    assert len(professor.historico(conn)) == 4
    with pytest.raises(Invalido):
        professor.conversar(conn, "  ")


def _questao_com_gabarito(conn):
    r = importador.gravar_prova(conn, importador.parse_prova(prova_sintetica()), titulo="p", sha256="y" * 64, nome_arquivo="p.pdf")
    return r


def test_quadrinhos_exigem_gabarito_e_usam_cache(conn):
    r = _questao_com_gabarito(conn)
    qid = conn.execute("SELECT id FROM questoes LIMIT 1").fetchone()[0]
    ia.definir_provedor_de_teste(Falso("{}"))
    with pytest.raises(Invalido):
        professor.quadrinhos(conn, qid)
    g = gabaritos.armazenar(conn, _gab70("B"), descricao="g", esperado=70)[0]["gabarito_id"]
    gabaritos.aplicar(conn, g, r["documento_id"], "conferência dos testes automatizados")
    resp = '{"quadros":[' + ",".join('{"titulo":"t","cena":"c","fala":"f","destaque":"d"}' for _ in range(4)) + "]}"
    f = Falso(resp)
    ia.definir_provedor_de_teste(f)
    a = professor.quadrinhos(conn, qid)
    b = professor.quadrinhos(conn, qid)
    assert len(a["quadros"]) == 4 and a["do_cache"] is False and b["do_cache"] is True and len(f.chamadas) == 1
    assert "alternativa B" in f.chamadas[0][1][0]["content"]
    ia.definir_provedor_de_teste(Falso('{"quadros":[{"fala":"só um"}]}'))
    with pytest.raises(ia.IaIndisponivel):
        professor.quadrinhos(conn, qid, regenerar=True)


def test_redacao_envio_valida_conteudo(conn, uploads):
    with pytest.raises(Invalido):
        redacao.salvar_envio(conn, b"%PDF-1.4 nao e imagem", "tema")
    with pytest.raises(Invalido):
        redacao.salvar_envio(conn, b"", "tema")
    rid = redacao.salvar_envio(conn, PNG, "Tema X")["redacao_id"]
    assert redacao.obter(conn, rid)["status"] == "pendente"


def test_redacao_so_envia_com_autorizacao(conn, uploads):
    rid = redacao.salvar_envio(conn, PNG, "Tema X")["redacao_id"]
    f = Falso("{}")
    ia.definir_provedor_de_teste(f)
    with pytest.raises(Conflito):
        redacao.corrigir(conn, rid, autorizo_envio=False)
    assert f.chamadas == []                             # nada saiu


def test_redacao_correcao_com_criterios_do_edital_e_nota_zero(conn, uploads):
    rid = redacao.salvar_envio(conn, PNG, "Tema X")["redacao_id"]
    rel = ('{"transcricao":"texto","criterios":{},"situacoes_de_nota_zero":[{"item":"8h","ocorre":true,"justificativa":"6 linhas"}],'
           '"nota_estimada_0_a_40":30,"pontos_a_melhorar":["x"]}')
    f = Falso(rel)
    ia.definir_provedor_de_teste(f)
    r = redacao.corrigir(conn, rid, autorizo_envio=True)
    assert r["nota_estimada"] == 0.0 and "sem valor oficial" in r["aviso"]
    sistema, _, img = f.chamadas[0]
    assert img.tipo_mime == "image/png"
    assert "40 (quarenta)" in sistema and "a) fugir ao tema" in sistema
    assert redacao.obter(conn, rid)["status"] == "corrigida"


def test_prompt_exportavel_traz_criterios():
    p = redacao.prompt_para_copiar("Tema")
    assert "Tema: avalia-se" in p and "nota 0 (zero)" in p
