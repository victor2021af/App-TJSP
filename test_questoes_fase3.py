import pytest

from app.errors import Conflito, Invalido
from app.services import gabaritos, importador, questoes, revisao, simulados
from app.services.conteudo import definir_status
from tests.conftest import utc

SECOES = [("LÍNgUA PORTUgUESA", 16), ("DIREItO PEnal", 30), ("atUalIDaDEs", 4), ("matEmÁtICa", 4),
          ("InfORmÁtICa", 9), ("RaCIOCínIO lógICO", 7)]


def prova_sintetica(n_extra: int = 0) -> str:
    """Prova de 70 questões gerada, com os artefatos reais: cabeçalho de página, marca d'água, hifenização."""
    linhas = ["=====PAGINA 1=====", "001. PROvA OBJETIvA", "=====PAGINA 2=====", "TJSP2301/001-EscreventeTécnicoJudiciárioConfidencial até o momento da aplicação."]
    n = 0
    for titulo, qtd in SECOES:
        linhas.append(titulo)
        if titulo.startswith("LÍN"):
            linhas.append("Leia o texto para responder às questões de números 01 a 02.")
            linhas += ["Texto-base com pou-", "pança e outra linha."]
        for _ in range(qtd):
            n += 1
            pre = "RAScUNHO" if n == 5 else ""
            linhas += [f"{pre}{n:02d}. Enunciado da questão número {n} com conteú-", "do suficiente para valer."]
            linhas += [f"({l}) Texto da alternativa {l} da {n}." for l in "ABCDE"]
            if n % 20 == 0:
                linhas += ["=====PAGINA %d=====" % (n // 20 + 2), "7", "TJSP2301/001-EscreventeTécnicoJudiciárioConfidencial até o momento da aplicação."]
    return "\n".join(linhas)


@pytest.fixture
def prova(conn):
    qs = importador.parse_prova(prova_sintetica())
    r = importador.gravar_prova(conn, qs, titulo="Prova sintética", sha256="x" * 64, ano=2023, nome_arquivo="sintetica.pdf")
    conn.commit()
    return r


def test_parser_cobre_70_e_ignora_capa_e_cabecalho():
    qs = importador.parse_prova(prova_sintetica())
    assert [q.numero for q in qs] == list(range(1, 71))
    assert all(set(q.alternativas) == set("ABCDE") for q in qs)
    assert "conteúdo" in qs[0].enunciado            # hifenização removida
    assert qs[4].numero == 5 and qs[4].enunciado.startswith("Enunciado")  # marca d'água removida
    assert "poupança" in qs[0].texto_apoio and qs[1].texto_apoio == qs[0].texto_apoio and qs[2].texto_apoio is None


def test_parser_disciplina_por_faixa():
    qs = {q.numero: q.secao for q in importador.parse_prova(prova_sintetica())}
    assert qs[1] == "portugues" and qs[16] == "portugues" and qs[17] == "direito_penal"
    assert qs[47] == "atualidades" and qs[51] == "matematica" and qs[70] == "raciocinio_logico"


def test_importacao_sem_gabarito_e_idempotente(conn, prova):
    assert prova["questoes"] == 70
    assert conn.execute("SELECT COUNT(*) FROM questoes WHERE gabarito IS NOT NULL").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM questoes WHERE precisa_revisao_manual=1").fetchone()[0] == 70
    assert conn.execute("SELECT COUNT(*) FROM alternativas").fetchone()[0] == 350
    qs = importador.parse_prova(prova_sintetica())
    again = importador.gravar_prova(conn, qs, titulo="x", sha256="x" * 64)
    assert again["ja_importado"] and conn.execute("SELECT COUNT(*) FROM questoes").fetchone()[0] == 70


def test_gabarito_parse_versoes():
    txt = "VERSÃO 1\n" + "\n".join(f"{i} - A" for i in range(1, 4)) + "\nVERSÃO 2\n1-B  2 - C"
    assert gabaritos.parse_gabarito(txt) == {"1": {1: "A", 2: "A", 3: "A"}, "2": {1: "B", 2: "C"}}
    with pytest.raises(Invalido):
        gabaritos.parse_gabarito("1 - A\n1 - B")


def _gab70(letra="C"):
    return "\n".join(f"{i} - {letra}" for i in range(1, 71))


def test_gabarito_incompleto_rejeitado(conn):
    with pytest.raises(Invalido):
        gabaritos.armazenar(conn, "1 - A\n2 - B", descricao="x", esperado=70)


def test_aplicar_exige_conferencia_e_mesmo_total(conn, prova):
    g = gabaritos.armazenar(conn, _gab70(), descricao="G", esperado=70)[0]["gabarito_id"]
    with pytest.raises(Invalido):
        gabaritos.aplicar(conn, g, prova["documento_id"], "ok")
    gabaritos.aplicar(conn, g, prova["documento_id"], "conferi 4 questões de matemática")
    assert conn.execute("SELECT COUNT(*) FROM questoes WHERE gabarito='C'").fetchone()[0] == 70
    assert conn.execute("SELECT COUNT(*) FROM questoes WHERE precisa_revisao_manual=1").fetchone()[0] == 0
    with pytest.raises(Conflito):
        gabaritos.aplicar(conn, g, prova["documento_id"], "conferi de novo, outra vez")


def test_gabarito_de_outro_tamanho_nao_aplica(conn, prova):
    g = gabaritos.armazenar(conn, "\n".join(f"{i} - A" for i in range(1, 11)), descricao="G", esperado=10)[0]["gabarito_id"]
    with pytest.raises(Conflito):
        gabaritos.aplicar(conn, g, prova["documento_id"], "tentativa de aplicar total errado")


def _com_gabarito(conn, prova):
    g = gabaritos.armazenar(conn, _gab70("B"), descricao="G", esperado=70)[0]["gabarito_id"]
    gabaritos.aplicar(conn, g, prova["documento_id"], "conferência feita nos testes")
    conn.commit()


def test_responder_sem_gabarito_recusa(conn, prova):
    qid = conn.execute("SELECT id FROM questoes LIMIT 1").fetchone()[0]
    with pytest.raises(Conflito):
        questoes.responder(conn, qid, "A")


def test_responder_corrige_e_estatisticas(conn, prova):
    _com_gabarito(conn, prova)
    ids = [r[0] for r in conn.execute("SELECT id FROM questoes ORDER BY id LIMIT 3")]
    assert questoes.responder(conn, ids[0], "b")["correta"] is True
    r = questoes.responder(conn, ids[1], "A", tipo_erro="interpretacao")
    assert r["correta"] is False and r["gabarito"] == "B"
    est = questoes.estatisticas(conn)
    assert est["feitas"] == 2 and est["acertos"] == 1 and est["aproveitamento"] == 50.0
    assert est["tipos_de_erro"] == {"interpretacao": 1}
    assert questoes.obter(conn, ids[2])["tem_gabarito"] and "gabarito" not in questoes.obter(conn, ids[2])
    assert questoes.listar(conn, erradas=True)["total"] == 1
    assert questoes.listar(conn, nao_respondidas=True)["total"] == 68
    questoes.favoritar(conn, ids[0], True)
    assert questoes.listar(conn, favoritas=True)["total"] == 1
    with pytest.raises(Invalido):
        questoes.responder(conn, ids[2], "Z")


def test_estatisticas_vazias(conn):
    e = questoes.estatisticas(conn)
    assert e["feitas"] == 0 and e["aproveitamento"] is None and e["por_disciplina"] == []


def test_simulado_completo_70_distribuicao(conn, prova):
    _com_gabarito(conn, prova)
    # prova sintética só tem 16 de português e 30 de "direito_penal" -> distribuição bate com o edital
    s = simulados.montar_completo(conn, semente=1, now=utc(2026, 1, 1, 10))
    assert s["total"] == 70
    cont = {r["codigo"]: r["n"] for r in conn.execute(
        """SELECT d.codigo, COUNT(*) n FROM simulado_questoes sq JOIN questoes q ON q.id=sq.questao_id
           JOIN disciplinas d ON d.id=q.disciplina_id GROUP BY d.codigo""")}
    assert cont == {"portugues": 16, "direito_penal": 30, "atualidades": 4, "matematica": 4, "informatica": 9, "raciocinio_logico": 7}
    sim = simulados.obter(conn, s["simulado_id"])
    for q in sim["questoes"][:20]:
        assert "gabarito" not in simulados.responder(conn, s["simulado_id"], q["questao_id"], "B")
    with pytest.raises(Conflito):
        simulados.responder(conn, s["simulado_id"], sim["questoes"][0]["questao_id"], "B")
    res = simulados.finalizar(conn, s["simulado_id"], now=utc(2026, 1, 1, 12))
    assert res["acertos"] == 20 and res["em_branco"] == 50 and res["segundos_usados"] == 7200
    assert set(res["blocos"]) == {"I_lingua_portuguesa", "II_direito"}


def test_simulado_completo_recusa_banco_insuficiente(conn):
    with pytest.raises(Conflito) as e:
        simulados.montar_completo(conn)
    assert "Banco insuficiente" in e.value.mensagem


def test_revisao_espacada_e_adaptativa(conn):
    a = conn.execute("SELECT id FROM assuntos LIMIT 1").fetchone()[0]
    definir_status(conn, a, "estudado", now=utc(2026, 1, 1, 8))
    assert revisao.pendentes(conn, now=utc(2026, 1, 1, 9)) == []
    p = revisao.pendentes(conn, now=utc(2026, 1, 2, 9))
    assert len(p) == 1 and p[0]["intervalo_dias"] == 1
    definir_status(conn, a, "estudado", now=utc(2026, 1, 1, 9))          # não duplica
    assert len(revisao.pendentes(conn, now=utc(2026, 2, 1), incluir_futuras=True)) == 1
    r = revisao.concluir(conn, p[0]["id"], 90, now=utc(2026, 1, 2, 9))
    assert r["proxima_etapa"] == 1 and r["proxima_em_dias"] == 7
    nxt = revisao.pendentes(conn, now=utc(2026, 1, 9, 10))[0]
    r = revisao.concluir(conn, nxt["id"], 70, now=utc(2026, 1, 9, 10))     # 60–79: repete com metade
    assert r["proxima_etapa"] == 1 and r["proxima_em_dias"] == 3
    nxt = revisao.pendentes(conn, now=utc(2026, 1, 13))[0]
    r = revisao.concluir(conn, nxt["id"], 40, now=utc(2026, 1, 13))        # <60: volta ao início e pede reforço
    assert r["proxima_etapa"] == 0
    assert conn.execute("SELECT status FROM progresso_assunto WHERE assunto_id=?", (a,)).fetchone()[0] == "necessita_reforco"


def test_ciclo_encerra_apos_30_dias(conn):
    a = conn.execute("SELECT id FROM assuntos LIMIT 1").fetchone()[0]
    revisao.agendar_se_necessario(conn, a, now=utc(2026, 1, 1))
    t, fim = utc(2026, 1, 2), None
    for _ in range(4):
        rid = revisao.pendentes(conn, now=t + __import__("datetime").timedelta(days=400))[0]["id"]
        fim = revisao.concluir(conn, rid, 95, now=t)
    assert fim["ciclo_encerrado"] is True
