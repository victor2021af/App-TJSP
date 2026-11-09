import { useEffect, useState } from "react";
import { ApiError, ROTULO_STATUS, api, type Assunto, type Bloco, type Disciplina, type StatusAssunto } from "../api";
import type { Preset } from "./Estudar";

const ORDEM_STATUS = Object.keys(ROTULO_STATUS) as StatusAssunto[];

function ListaAssuntos({ disciplina, aoVoltar, aoEstudar }: { disciplina: Disciplina; aoVoltar: () => void; aoEstudar: (p: Preset) => void }) {
  const [assuntos, setAssuntos] = useState<Assunto[] | null>(null);
  const [aberto, setAberto] = useState<number | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    api.get<Assunto[]>(`/disciplinas/${disciplina.id}/assuntos`).then(setAssuntos).catch((e: unknown) => setErro(e instanceof ApiError ? e.message : "Erro ao carregar."));
  }, [disciplina.id]);

  async function mudar(id: number, status: StatusAssunto) {
    setErro(null);
    try {
      await api.put(`/assuntos/${id}/status`, { status });
      setAssuntos((atual) => atual?.map((a) => (a.id === id ? { ...a, status } : a)) ?? null);
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : "Erro ao salvar.");
    }
  }

  return (
    <>
      <button onClick={aoVoltar}>← Voltar</button>
      <h1>{disciplina.nome}</h1>
      {disciplina.descricao_edital && <p className="suave">{disciplina.descricao_edital}</p>}
      {erro && <p className="erro" role="alert">{erro}</p>}
      {!assuntos ? (
        <p className="suave">Carregando…</p>
      ) : (
        <ul className="assuntos">
          {assuntos.map((a) => (
            <li key={a.id} className="cartao">
              <div className="linha-assunto">
                <button className="link" onClick={() => setAberto(aberto === a.id ? null : a.id)} aria-expanded={aberto === a.id}>
                  {a.ref_edital ? `${a.ref_edital}. ` : ""}{a.titulo}
                </button>
                <select value={a.status} onChange={(e) => void mudar(a.id, e.target.value as StatusAssunto)} aria-label={`Situação de ${a.titulo}`}>
                  {ORDEM_STATUS.map((s) => <option key={s} value={s}>{ROTULO_STATUS[s]}</option>)}
                </select>
              </div>
              {aberto === a.id && (
                <div>
                  <p className="trecho"><span className="suave">Texto do edital:</span> {a.texto_edital}</p>
                  <button onClick={() => aoEstudar({ disciplinaId: disciplina.id, assuntoId: a.id })}>Estudar este assunto</button>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

export function Conteudo({ aoEstudar }: { aoEstudar: (p: Preset) => void }) {
  const [blocos, setBlocos] = useState<Bloco[] | null>(null);
  const [escolhida, setEscolhida] = useState<Disciplina | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    api.get<Bloco[]>("/conteudo").then(setBlocos).catch((e: unknown) => setErro(e instanceof ApiError ? e.message : "Erro ao carregar."));
  }, [escolhida]);

  if (erro) return <p className="erro" role="alert">{erro}</p>;
  if (!blocos) return <p className="suave">Carregando…</p>;
  if (escolhida) return <ListaAssuntos disciplina={escolhida} aoVoltar={() => setEscolhida(null)} aoEstudar={aoEstudar} />;

  return (
    <>
      <h1>Conteúdo programático</h1>
      <p className="suave">Estrutura do Edital TJSP nº 02/2026 (Anexo VIII). Nenhum assunto foi acrescentado além do edital.</p>
      {blocos.map((b) => (
        <section key={b.id}>
          <h2>
            Bloco {b.codigo} — {b.nome} <span className="suave">({b.num_questoes} questões)</span>
          </h2>
          <p className="suave">
            {b.eliminatorio ? `Eliminatório: mínimo de ${b.minimo_acertos_pct}% de acertos no bloco.` : "Apenas classificatório."}
          </p>
          <div className="grade">
            {b.disciplinas.map((d) => {
              const feitos = d.status_contagem.estudado + d.status_contagem.em_revisao + d.status_contagem.dominado;
              const p = d.assuntos_total ? Math.round((100 * feitos) / d.assuntos_total) : 0;
              return (
                <button key={d.id} className="cartao disciplina" onClick={() => setEscolhida(d)}>
                  <strong>{d.nome}</strong>
                  <span className="suave">
                    {d.num_questoes ? `${d.num_questoes} questões · ` : ""}{d.assuntos_total} assuntos
                  </span>
                  <div className="barra" aria-hidden="true"><div style={{ width: `${p}%` }} /></div>
                  <span className="suave">{feitos} de {d.assuntos_total} concluídos</span>
                </button>
              );
            })}
          </div>
        </section>
      ))}
    </>
  );
}
