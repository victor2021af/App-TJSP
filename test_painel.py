from datetime import timedelta

from app.services import configuracoes, conteudo, estudo
from app.services.painel import _sequencia, painel
from conftest import utc

# 08/11/2026 15:00 UTC = 12:00 em São Paulo (UTC-3)
NOW = utc(2026, 11, 8, 15, 0, 0)


def test_estado_zerado_nao_inventa_numeros(conn):
    p = painel(conn, NOW)
    assert p["estudo"]["total_segundos"] == 0 and p["estudo"]["hoje_segundos"] == 0
    assert p["estudo"]["sequencia_dias"] == 0
    assert p["questoes"]["respondidas"] == 0
    assert p["questoes"]["acerto_pct"] is None            # não é 0%: ainda não há dado
    assert p["indicador_preparo"]["acerto_pct"] is None
    assert p["estudo"]["meta_diaria_cumprida_pct"] is None
    assert p["conteudo"]["concluido_pct"] == 0.0
    assert p["ultimos_assuntos"] == [] and p["proximas_revisoes"] == []
    assert "aprovação" in p["indicador_preparo"]["descricao"]


def test_horas_hoje_total_e_por_disciplina(conn):
    d = conn.execute("SELECT id FROM disciplinas WHERE codigo='direito_penal'").fetchone()["id"]
    s = estudo.iniciar(conn, disciplina_id=d, now=NOW - timedelta(hours=2))
    estudo.finalizar(conn, s["id"], now=NOW - timedelta(hours=1))        # 1 h hoje
    s = estudo.iniciar(conn, disciplina_id=d, now=NOW - timedelta(days=2, hours=1))
    estudo.finalizar(conn, s["id"], now=NOW - timedelta(days=2))          # 1 h anteontem
    p = painel(conn, NOW)
    assert p["estudo"]["hoje_segundos"] == 3600
    assert p["estudo"]["total_segundos"] == 7200
    assert p["estudo"]["por_disciplina"][0]["nome"] == "Direito Penal"
    assert p["estudo"]["sequencia_dias"] == 1  # anteontem e hoje, ontem vazio


def test_sessao_em_andamento_conta_no_painel(conn):
    estudo.iniciar(conn, now=NOW - timedelta(minutes=30))
    assert painel(conn, NOW)["estudo"]["hoje_segundos"] == 1800


def test_meta_diaria(conn):
    configuracoes.atualizar(conn, {"meta_diaria_minutos": 120})
    s = estudo.iniciar(conn, now=NOW - timedelta(minutes=60))
    estudo.finalizar(conn, s["id"], now=NOW)
    p = painel(conn, NOW)
    assert p["estudo"]["meta_diaria_minutos"] == 120
    assert p["estudo"]["meta_diaria_cumprida_pct"] == 50


def test_fuso_define_o_dia(conn):
    # 01:30 UTC de 09/11 ainda é 22:30 de 08/11 em São Paulo.
    s = estudo.iniciar(conn, now=utc(2026, 11, 9, 0, 30))
    estudo.finalizar(conn, s["id"], now=utc(2026, 11, 9, 1, 30))
    p = painel(conn, utc(2026, 11, 9, 2, 0))
    assert p["estudo"]["hoje_segundos"] == 3600


def test_sequencia_de_dias():
    from datetime import date
    h = date(2026, 11, 8)
    assert _sequencia(set(), h) == 0
    assert _sequencia({h, h - timedelta(1), h - timedelta(2)}, h) == 3
    assert _sequencia({h - timedelta(1), h - timedelta(2)}, h) == 2    # hoje ainda não estudou
    assert _sequencia({h - timedelta(3)}, h) == 0                      # quebrou a sequência


def test_questoes_e_acerto_pct(conn):
    conn.execute("INSERT INTO questoes (origem, enunciado, criada_em) VALUES ('manual','q','2026-11-08T00:00:00Z')")
    for ok in (1, 1, 0):
        conn.execute("INSERT INTO tentativas (questao_id, alternativa, correta, tempo_segundos, respondida_em)"
                     " VALUES (1,'A',?,60,'2026-11-08T10:00:00Z')", (ok,))
    conn.commit()
    q = painel(conn, NOW)["questoes"]
    assert (q["respondidas"], q["acertos"], q["erros"]) == (3, 2, 1)
    assert q["acerto_pct"] == 66.7 and q["tempo_medio_segundos"] == 60


def test_conteudo_concluido_considera_estudado_revisao_e_dominado(conn):
    ids = [r["id"] for r in conn.execute("SELECT id FROM assuntos ORDER BY id LIMIT 4")]
    for i, st in zip(ids, ("estudado", "em_revisao", "dominado", "necessita_reforco")):
        conteudo.definir_status(conn, i, st)
    total = painel(conn, NOW)["conteudo"]["total_assuntos"]
    assert painel(conn, NOW)["conteudo"]["concluido_pct"] == round(100 * 3 / total, 1)


def test_sugestao_segue_prioridade_e_ordem_do_edital(conn):
    s = painel(conn, NOW)["sugestao_automatica"]
    # Prioridade 1 e primeiro bloco na ordem do edital => Língua Portuguesa, item 1.
    assert s["disciplina"] == "Língua Portuguesa"
    assert s["titulo"] == "Compreensão e interpretação de textos"
    conteudo.definir_status(conn, s["assunto_id"], "estudado")
    assert painel(conn, NOW)["sugestao_automatica"]["titulo"] == "Informações literais e inferências"
