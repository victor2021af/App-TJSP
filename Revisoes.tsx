import { useCallback, useEffect, useState } from "react";
import { ApiError, api } from "../api";

interface Rev { id: number; assunto: string; disciplina: string; etapa: number; devida_em: string; atrasada: boolean; intervalo_dias: number }

export function Revisoes() {
  const [lista, setLista] = useState<Rev[] | null>(null);
  const [futuras, setFuturas] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const carregar = useCallback(async () => {
    try { setLista(await api.get(`/revisoes?futuras=${futuras}`)); } catch (e) { setMsg(e instanceof ApiError ? e.message : "Erro."); }
  }, [futuras]);
  useEffect(() => { void carregar(); }, [carregar]);

  async function concluir(id: number, acerto: number | null) {
    const r = await api.post<{ proxima_em_dias: number | null; ciclo_encerrado: boolean }>(`/revisoes/${id}/concluir`, { acerto_pct: acerto });
    setMsg(r.ciclo_encerrado ? "Ciclo de revisões concluído para este assunto." : `Próxima revisão em ${r.proxima_em_dias} dia(s).`);
    await carregar();
  }

  return (
    <>
      <h1>Revisões</h1>
      <p className="suave">Intervalos de 1, 7, 15 e 30 dias após marcar o assunto como estudado. Acerto abaixo de 80% repete a etapa; abaixo de 60% recomeça.</p>
      <label><input type="checkbox" checked={futuras} onChange={(e) => setFuturas(e.target.checked)} style={{ width: "auto", minHeight: 0 }} /> Mostrar também as futuras</label>
      {msg && <p className="ok" role="status">{msg}</p>}
      {lista?.length === 0 && <p className="suave">Nenhuma revisão pendente. Marque assuntos como "Estudado" em Conteúdo para agendar.</p>}
      <ul className="lista-simples">
        {lista?.map((r) => (
          <li key={r.id}>
            <span><strong>{r.disciplina}</strong> — {r.assunto}<br />
              <span className={r.atrasada ? "erro" : "suave"}>{r.atrasada ? "Atrasada · " : ""}devida em {new Date(r.devida_em).toLocaleDateString("pt-BR")} (etapa {r.etapa + 1}/4)</span>
            </span>
            {r.atrasada && (
              <span className="linha-botoes">
                <button onClick={() => concluir(r.id, 90)}>Fui bem (≥80%)</button>
                <button onClick={() => concluir(r.id, 70)}>Médio</button>
                <button onClick={() => concluir(r.id, 40)}>Fui mal</button>
              </span>
            )}
          </li>
        ))}
      </ul>
    </>
  );
}
