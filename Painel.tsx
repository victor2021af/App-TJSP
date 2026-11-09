import { useEffect, useState } from "react";
import { ApiError, api, type Painel as DadosPainel } from "../api";
import { dataHora, duracao, pct } from "../format";
import type { Preset } from "./Estudar";

function saudacao(): string {
  const h = new Date().getHours();
  return h < 12 ? "Bom dia" : h < 18 ? "Boa tarde" : "Boa noite";
}

function Barra({ valor }: { valor: number | null }) {
  return (
    <div className="barra" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={valor ?? 0}>
      <div style={{ width: `${Math.min(100, valor ?? 0)}%` }} />
    </div>
  );
}

export function Painel({ nome, aoEstudar }: { nome: string; aoEstudar: (p: Preset) => void }) {
  const [dados, setDados] = useState<DadosPainel | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    api.get<DadosPainel>("/painel").then(setDados).catch((e: unknown) => setErro(e instanceof ApiError ? e.message : "Erro ao carregar."));
  }, []);

  if (erro) return <p className="erro" role="alert">{erro}</p>;
  if (!dados) return <p className="suave">Carregando painel…</p>;

  const { estudo, questoes, conteudo, indicador_preparo: preparo } = dados;
  const semHistorico = estudo.total_segundos === 0 && questoes.respondidas === 0;

  return (
    <>
      <h1>{saudacao()}{nome ? `, ${nome}` : ""}.</h1>
      {semHistorico && (
        <p className="aviso">
          Ainda não há horas nem questões registradas. Os números abaixo começam do zero e só mostram o que você realmente fizer.
        </p>
      )}

      <div className="grade">
        <section className="cartao">
          <h2>Hoje</h2>
          <p className="numero">{duracao(estudo.hoje_segundos)}</p>
          {estudo.meta_diaria_minutos ? (
            <>
              <Barra valor={estudo.meta_diaria_cumprida_pct} />
              <p className="suave">{pct(estudo.meta_diaria_cumprida_pct)} da meta de {estudo.meta_diaria_minutos} min</p>
            </>
          ) : (
            <p className="suave">Defina uma meta diária em Ajustes.</p>
          )}
        </section>

        <section className="cartao">
          <h2>Sequência</h2>
          <p className="numero">{estudo.sequencia_dias} {estudo.sequencia_dias === 1 ? "dia" : "dias"}</p>
          <p className="suave">Total estudado: {duracao(estudo.total_segundos)}</p>
        </section>

        <section className="cartao">
          <h2>Questões</h2>
          <p className="numero">{questoes.respondidas}</p>
          <p className="suave">
            {questoes.respondidas === 0
              ? "O banco de questões chega na próxima fase."
              : `${questoes.acertos} acertos · ${questoes.erros} erros · ${pct(questoes.acerto_pct)}`}
          </p>
        </section>

        <section className="cartao">
          <h2>Conteúdo concluído</h2>
          <p className="numero">{pct(conteudo.concluido_pct)}</p>
          <Barra valor={conteudo.concluido_pct} />
          <p className="suave">{conteudo.total_assuntos} assuntos do edital</p>
        </section>
      </div>

      <section className="cartao">
        <h2>Indicador de preparo</h2>
        <p className="suave">{preparo.descricao}</p>
        <ul className="lista-simples">
          <li><span>Conteúdo concluído</span><strong>{pct(preparo.conteudo_concluido_pct)}</strong></li>
          <li><span>Meta de hoje</span><strong>{pct(preparo.meta_do_dia_pct)}</strong></li>
          <li><span>Acerto nas questões</span><strong>{pct(preparo.acerto_pct)}</strong></li>
        </ul>
      </section>

      {dados.sugestao_automatica && (
        <section className="cartao destaque">
          <h2>Sugestão para estudar agora</h2>
          <p><strong>{dados.sugestao_automatica.disciplina}</strong> — {dados.sugestao_automatica.titulo}</p>
          <p className="suave">{dados.sugestao_automatica.motivo}</p>
          <button
            className="primario"
            onClick={() => aoEstudar({ disciplinaId: dados.sugestao_automatica!.disciplina_id, assuntoId: dados.sugestao_automatica!.assunto_id })}
          >
            Estudar este assunto
          </button>
        </section>
      )}

      <div className="grade duas">
        <section className="cartao">
          <h2>Matérias prioritárias</h2>
          <ul className="lista-simples">
            {dados.materias_prioritarias.map((m) => (
              <li key={m.disciplina_id}><span>{m.nome}</span><strong>{pct(m.concluido_pct)}</strong></li>
            ))}
          </ul>
        </section>

        <section className="cartao">
          <h2>Últimos assuntos estudados</h2>
          {dados.ultimos_assuntos.length === 0 ? (
            <p className="suave">Nenhum assunto estudado ainda.</p>
          ) : (
            <ul className="lista-simples">
              {dados.ultimos_assuntos.map((u) => (
                <li key={u.id}><span>{u.assunto}</span><span className="suave">{dataHora(u.finalizada_em)}</span></li>
              ))}
            </ul>
          )}
        </section>

        <section className="cartao">
          <h2>Próximas revisões</h2>
          {dados.proximas_revisoes.length === 0 ? (
            <p className="suave">Nenhuma revisão agendada. A revisão espaçada chega na Fase 2.</p>
          ) : (
            <ul className="lista-simples">
              {dados.proximas_revisoes.map((r) => (
                <li key={r.id}><span>{r.assunto}</span><span className="suave">{dataHora(r.devida_em)}</span></li>
              ))}
            </ul>
          )}
        </section>

        <section className="cartao">
          <h2>Horas por disciplina</h2>
          {estudo.por_disciplina.length === 0 ? (
            <p className="suave">Sem horas registradas.</p>
          ) : (
            <ul className="lista-simples">
              {estudo.por_disciplina.map((d) => (
                <li key={d.disciplina_id ?? "x"}><span>{d.nome}</span><strong>{duracao(d.segundos)}</strong></li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </>
  );
}
