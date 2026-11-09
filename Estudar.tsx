import { useCallback, useEffect, useMemo, useState } from "react";
import { ApiError, api, type Assunto, type Bloco, type SessaoEstudo, type SessaoHistorico } from "../api";
import { dataHora, duracao, relogio } from "../format";

export interface Preset {
  disciplinaId?: number;
  assuntoId?: number;
}

/** Segundos decorridos, calculados a partir do que o servidor informou + o tempo local desde então. */
function useSegundos(sessao: SessaoEstudo | null): number {
  const base = useMemo(() => ({ seg: sessao?.segundos_decorridos ?? 0, em: Date.now() }), [sessao]);
  const [agora, setAgora] = useState(() => Date.now());
  const correndo = sessao?.cronometro_correndo ?? false;
  useEffect(() => {
    setAgora(Date.now());
    if (!correndo) return;
    const t = window.setInterval(() => setAgora(Date.now()), 500);
    return () => window.clearInterval(t);
  }, [correndo, sessao]);
  if (!sessao) return 0;
  return base.seg + (correndo ? Math.max(0, Math.floor((agora - base.em) / 1000)) : 0);
}

export function Estudar({ preset }: { preset: Preset | null }) {
  const [sessao, setSessao] = useState<SessaoEstudo | null>(null);
  const [carregou, setCarregou] = useState(false);
  const [blocos, setBlocos] = useState<Bloco[]>([]);
  const [assuntos, setAssuntos] = useState<Assunto[]>([]);
  const [disciplinaId, setDisciplinaId] = useState<number | "">(preset?.disciplinaId ?? "");
  const [assuntoId, setAssuntoId] = useState<number | "">(preset?.assuntoId ?? "");
  const [objetivo, setObjetivo] = useState("");
  const [encerrando, setEncerrando] = useState(false);
  const [cumprido, setCumprido] = useState<boolean | null>(null);
  const [observacao, setObservacao] = useState("");
  const [historico, setHistorico] = useState<SessaoHistorico[]>([]);
  const [erro, setErro] = useState<string | null>(null);

  const segundos = useSegundos(sessao);
  const disciplinas = useMemo(() => blocos.flatMap((b) => b.disciplinas), [blocos]);

  const carregarHistorico = useCallback(() => {
    api.get<SessaoHistorico[]>("/estudo/sessoes?limite=15").then(setHistorico).catch(() => undefined);
  }, []);

  useEffect(() => {
    Promise.all([api.get<SessaoEstudo | null>("/estudo/sessao-ativa"), api.get<Bloco[]>("/conteudo")])
      .then(([s, b]) => {
        setSessao(s);
        setBlocos(b);
      })
      .catch((e: unknown) => setErro(e instanceof ApiError ? e.message : "Erro ao carregar."))
      .finally(() => setCarregou(true));
    carregarHistorico();
  }, [carregarHistorico]);

  useEffect(() => {
    if (disciplinaId === "") {
      setAssuntos([]);
      return;
    }
    api.get<Assunto[]>(`/disciplinas/${disciplinaId}/assuntos`).then(setAssuntos).catch(() => setAssuntos([]));
  }, [disciplinaId]);

  async function acao<T>(fn: () => Promise<T>): Promise<T | undefined> {
    setErro(null);
    try {
      return await fn();
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : "Erro inesperado.");
      return undefined;
    }
  }

  async function iniciar() {
    const s = await acao(() =>
      api.post<SessaoEstudo>("/estudo/sessoes", {
        disciplina_id: disciplinaId === "" ? null : disciplinaId,
        assunto_id: assuntoId === "" ? null : assuntoId,
        objetivo: objetivo.trim() || null,
      }),
    );
    if (s) setSessao(s);
  }

  async function pausarOuRetomar() {
    if (!sessao) return;
    const s = await acao(() => api.post<SessaoEstudo>(`/estudo/sessoes/${sessao.id}/${sessao.cronometro_correndo ? "pausar" : "retomar"}`));
    if (s) setSessao(s);
  }

  async function finalizar() {
    if (!sessao) return;
    const s = await acao(() =>
      api.post<SessaoEstudo>(`/estudo/sessoes/${sessao.id}/finalizar`, { objetivo_cumprido: cumprido, observacao: observacao.trim() || null }),
    );
    if (s) {
      setSessao(null);
      setEncerrando(false);
      setCumprido(null);
      setObservacao("");
      setObjetivo("");
      carregarHistorico();
    }
  }

  if (!carregou) return <p className="suave">Carregando…</p>;

  const nomeDisciplina = sessao?.disciplina_id ? disciplinas.find((d) => d.id === sessao.disciplina_id)?.nome : null;

  return (
    <>
      <h1>Estudar</h1>
      {erro && <p className="erro" role="alert">{erro}</p>}

      {sessao ? (
        <section className="cartao cronometro">
          <p className="suave">{nomeDisciplina ?? "Sessão livre"}{sessao.objetivo ? ` · ${sessao.objetivo}` : ""}</p>
          <p className="relogio" aria-live="off">{relogio(segundos)}</p>
          <p className="suave">{sessao.cronometro_correndo ? "Contando tempo efetivo de estudo" : "Pausado — o tempo parado não conta"}</p>
          {!encerrando ? (
            <div className="acoes">
              <button className="grande" onClick={pausarOuRetomar}>{sessao.cronometro_correndo ? "Pausar" : "Retomar"}</button>
              <button className="grande primario" onClick={() => setEncerrando(true)}>Finalizar</button>
            </div>
          ) : (
            <div className="formulario">
              <p>Você cumpriu o objetivo desta sessão?</p>
              <div className="acoes">
                <button className={cumprido === true ? "marcado" : ""} onClick={() => setCumprido(true)}>Sim</button>
                <button className={cumprido === false ? "marcado" : ""} onClick={() => setCumprido(false)}>Em parte / não</button>
              </div>
              <label>
                Observação (opcional)
                <textarea value={observacao} onChange={(e) => setObservacao(e.target.value)} rows={3} maxLength={1000} />
              </label>
              <div className="acoes">
                <button onClick={() => setEncerrando(false)}>Voltar</button>
                <button className="primario" onClick={finalizar}>Salvar e encerrar</button>
              </div>
            </div>
          )}
        </section>
      ) : (
        <section className="cartao formulario">
          <h2>Nova sessão</h2>
          <label>
            Disciplina
            <select
              value={disciplinaId}
              onChange={(e) => {
                setDisciplinaId(e.target.value === "" ? "" : Number(e.target.value));
                setAssuntoId("");
              }}
            >
              <option value="">Sem disciplina específica</option>
              {blocos.map((b) => (
                <optgroup key={b.id} label={`Bloco ${b.codigo} — ${b.nome}`}>
                  {b.disciplinas.map((d) => <option key={d.id} value={d.id}>{d.nome}</option>)}
                </optgroup>
              ))}
            </select>
          </label>
          <label>
            Assunto
            <select value={assuntoId} onChange={(e) => setAssuntoId(e.target.value === "" ? "" : Number(e.target.value))} disabled={disciplinaId === ""}>
              <option value="">Sem assunto específico</option>
              {assuntos.map((a) => <option key={a.id} value={a.id}>{a.titulo}</option>)}
            </select>
          </label>
          <label>
            Objetivo da sessão
            <input value={objetivo} onChange={(e) => setObjetivo(e.target.value)} maxLength={300} placeholder="Ex.: fazer 20 questões de crase" />
          </label>
          <button className="grande primario" onClick={iniciar}>Iniciar cronômetro</button>
        </section>
      )}

      <section className="cartao">
        <h2>Sessões recentes</h2>
        {historico.length === 0 ? (
          <p className="suave">Nenhuma sessão concluída ainda.</p>
        ) : (
          <ul className="lista-simples">
            {historico.map((h) => (
              <li key={h.id}>
                <span>
                  {h.assunto_titulo ?? h.disciplina_nome ?? "Sessão livre"}
                  {h.objetivo_cumprido === 1 && " ✓"}
                  <br />
                  <span className="suave">{dataHora(h.finalizada_em)}</span>
                </span>
                <strong>{duracao(h.segundos_acumulados)}</strong>
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  );
}
