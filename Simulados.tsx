import { useEffect, useState } from "react";
import { ApiError, api } from "../api";

interface Sim { id: number; titulo: string; tipo: string; iniciado_em: string; finalizado_em: string | null }
interface SimDet { id: number; titulo: string; tempo_limite_seg: number | null; iniciado_em: string; finalizado_em: string | null; questoes: { posicao: number; questao_id: number; resposta: string | null }[] }
interface Q { id: number; texto_apoio: string | null; enunciado: string; alternativas: { letra: string; texto: string }[]; disciplina_nome: string | null }
interface Res { titulo: string; total: number; acertos: number; em_branco: number; segundos_usados: number | null;
  por_disciplina: { nome: string; total: number; acertos: number; em_branco: number }[];
  blocos?: Record<string, { acertos: number; total: number; minimo: number; atingiu_minimo: boolean }>; observacao?: string }

export function Simulados() {
  const [lista, setLista] = useState<Sim[]>([]);
  const [atual, setAtual] = useState<number | null>(null);
  const [resultado, setResultado] = useState<Res | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const carregar = () => api.get<Sim[]>("/simulados").then(setLista).catch(() => undefined);
  useEffect(() => { void carregar(); }, []);

  async function novo() {
    setMsg(null);
    try {
      const r = await api.post<{ simulado_id: number }>("/simulados", { tipo: "completo", somente_oficiais: true });
      setAtual(r.simulado_id);
    } catch (e) { setMsg(e instanceof ApiError ? e.message : "Erro."); }
  }
  async function ver(id: number, finalizado: boolean) {
    if (finalizado) setResultado(await api.get<Res>(`/simulados/${id}/resultado`)); else setAtual(id);
  }

  if (resultado) return <Resultado r={resultado} aoVoltar={() => { setResultado(null); void carregar(); }} />;
  if (atual !== null) return <Fazer id={atual} aoSair={() => { setAtual(null); void carregar(); }} aoFinalizar={(r) => { setAtual(null); setResultado(r); }} />;

  return (
    <>
      <h1>Simulados</h1>
      <section className="cartao">
        <h2>Simulado completo — 70 questões</h2>
        <p className="suave">Distribuição do edital 2026: 16 Português, 30 Direito, 4 Atualidades, 4 Matemática, 9 Informática, 7 Raciocínio Lógico.
          Usa só questões oficiais com gabarito comprovado; se o banco não tiver o suficiente, o app avisa em vez de completar com outra coisa.</p>
        <button className="primario" onClick={novo}>Montar simulado completo</button>
        {msg && <p className="erro" role="alert">{msg}</p>}
      </section>
      <h2>Histórico</h2>
      {lista.length === 0 && <p className="suave">Nenhum simulado ainda.</p>}
      <ul className="lista-simples">
        {lista.map((s) => (
          <li key={s.id}><button className="link" onClick={() => ver(s.id, !!s.finalizado_em)}>{s.titulo}</button>
            <span className="suave">{new Date(s.iniciado_em).toLocaleString("pt-BR")} · {s.finalizado_em ? "finalizado" : "em andamento"}</span></li>
        ))}
      </ul>
    </>
  );
}

function Fazer({ id, aoSair, aoFinalizar }: { id: number; aoSair: () => void; aoFinalizar: (r: Res) => void }) {
  const [sim, setSim] = useState<SimDet | null>(null);
  const [i, setI] = useState(0);
  const [q, setQ] = useState<Q | null>(null);
  const [escolha, setEscolha] = useState<string | null>(null);
  const [agora, setAgora] = useState(Date.now());
  const [msg, setMsg] = useState<string | null>(null);

  const carregar = () => api.get<SimDet>(`/simulados/${id}`).then(setSim);
  useEffect(() => { void carregar(); }, [id]);
  useEffect(() => { const t = setInterval(() => setAgora(Date.now()), 1000); return () => clearInterval(t); }, []);
  const questaoId = sim?.questoes[i]?.questao_id;
  useEffect(() => {
    if (!questaoId) return;
    setQ(null); setEscolha(null);
    api.get<Q>(`/questoes/${questaoId}`).then(setQ);
  }, [questaoId]);

  if (!sim) return <p className="suave">Carregando…</p>;
  const respondidas = sim.questoes.filter((x) => x.resposta).length;
  const restante = sim.tempo_limite_seg ? sim.tempo_limite_seg - Math.floor((agora - new Date(sim.iniciado_em).getTime()) / 1000) : null;
  const atualDet = sim.questoes[i];

  async function confirmar() {
    if (!escolha || !q) return;
    try {
      await api.post(`/simulados/${id}/responder`, { questao_id: q.id, alternativa: escolha });
      await carregar();
      if (i < sim!.questoes.length - 1) setI(i + 1);
    } catch (e) { setMsg(e instanceof ApiError ? e.message : "Erro."); }
  }
  async function finalizar() {
    const faltam = sim!.questoes.length - respondidas;
    if (faltam > 0 && !window.confirm(`Faltam ${faltam} questões em branco. Finalizar mesmo assim?`)) return;
    aoFinalizar(await api.post<Res>(`/simulados/${id}/finalizar`));
  }

  return (
    <>
      <button onClick={aoSair}>← Sair (continua salvo)</button>
      <h1>{sim.titulo}</h1>
      <p className="suave">Questão {i + 1}/{sim.questoes.length} · respondidas {respondidas}
        {restante !== null && ` · tempo restante ${Math.max(0, Math.floor(restante / 60))} min`}
        {restante !== null && restante < 0 && " (tempo esgotado — o app não bloqueia; é referência)"}</p>
      {q ? (
        <>
          {q.texto_apoio && <section className="cartao texto-apoio"><p>{q.texto_apoio}</p></section>}
          <p className="enunciado">{q.enunciado}</p>
          <div className="alternativas" role="radiogroup">
            {q.alternativas.map((a) => (
              <button key={a.letra} role="radio" aria-checked={(atualDet.resposta ?? escolha) === a.letra} disabled={!!atualDet.resposta}
                className={`alt ${(atualDet.resposta ?? escolha) === a.letra ? "marcado" : ""}`} onClick={() => setEscolha(a.letra)}>
                <strong>{a.letra}</strong> {a.texto}
              </button>
            ))}
          </div>
          {!atualDet.resposta && <button className="primario" disabled={!escolha} onClick={confirmar}>Confirmar resposta</button>}
          {atualDet.resposta && <p className="suave">Respondida (gabarito só no final).</p>}
        </>
      ) : <p className="suave">Carregando questão…</p>}
      {msg && <p className="erro" role="alert">{msg}</p>}
      <div className="linha-botoes">
        <button disabled={i === 0} onClick={() => setI(i - 1)}>Anterior</button>
        <button disabled={i >= sim.questoes.length - 1} onClick={() => setI(i + 1)}>Próxima</button>
        <button className="primario" onClick={finalizar}>Finalizar</button>
      </div>
    </>
  );
}

function Resultado({ r, aoVoltar }: { r: Res; aoVoltar: () => void }) {
  return (
    <>
      <button onClick={aoVoltar}>← Voltar</button>
      <h1>{r.titulo}</h1>
      <p><strong>{r.acertos}</strong> acertos em {r.total} ({Math.round((100 * r.acertos) / r.total)}%) · {r.em_branco} em branco
        {r.segundos_usados !== null && ` · ${Math.round(r.segundos_usados / 60)} min`}</p>
      {r.blocos && (
        <section className="cartao">
          <h2>Mínimos eliminatórios do edital (50%)</h2>
          {Object.entries(r.blocos).map(([k, b]) => (
            <p key={k} className={b.atingiu_minimo ? "ok" : "erro"}>{k.replace(/_/g, " ")}: {b.acertos}/{b.total} — {b.atingiu_minimo ? "atingiu" : "NÃO atingiu"} o mínimo ({b.minimo})</p>
          ))}
          {r.observacao && <p className="suave">{r.observacao}</p>}
        </section>
      )}
      <table className="tabela"><thead><tr><th>Disciplina</th><th>Acertos</th><th>Em branco</th></tr></thead>
        <tbody>{r.por_disciplina.map((d) => <tr key={d.nome}><td>{d.nome}</td><td>{d.acertos}/{d.total}</td><td>{d.em_branco}</td></tr>)}</tbody></table>
    </>
  );
}
