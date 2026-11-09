import { useCallback, useEffect, useState } from "react";
import { ApiError, api } from "../api";

interface Item {
  id: number; origem: string; ano: number | null; numero_original: number | null; enunciado: string;
  disciplina: string | null; disciplina_nome: string | null; tem_gabarito: boolean; favorita: boolean;
}
interface Alt { letra: string; texto: string }
interface Questao {
  id: number; origem: string; ano: number | null; numero_original: number | null; documento: string | null;
  texto_apoio: string | null; enunciado: string; alternativas: Alt[]; tem_gabarito: boolean; favorita: boolean;
  disciplina_nome: string | null;
}
interface Resultado { correta: boolean; gabarito: string; justificativa: string | null }
interface Quadro { titulo: string; cena: string; fala: string; destaque: string }

const DISCIPLINAS: [string, string][] = [
  ["", "Todas"], ["portugues", "Português"], ["direito_penal", "Direito Penal"],
  ["direito_processual_penal", "Proc. Penal"], ["direito_processual_civil", "Proc. Civil"],
  ["direito_constitucional", "Constitucional"], ["direito_administrativo", "Administrativo"],
  ["atualidades", "Atualidades"], ["matematica", "Matemática"], ["informatica", "Informática"],
  ["raciocinio_logico", "Raciocínio Lógico"],
];

export function Questoes() {
  const [disc, setDisc] = useState("");
  const [filtro, setFiltro] = useState("");
  const [busca, setBusca] = useState("");
  const [lista, setLista] = useState<{ total: number; itens: Item[] } | null>(null);
  const [abertaId, setAbertaId] = useState<number | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  const carregar = useCallback(async () => {
    const p = new URLSearchParams({ limite: "50" });
    if (disc) p.set("disciplina", disc);
    if (busca.trim()) p.set("busca", busca.trim());
    if (filtro === "gabarito") p.set("somente_com_gabarito", "true");
    if (filtro === "inedita") { p.set("nao_respondidas", "true"); p.set("somente_com_gabarito", "true"); }
    if (filtro === "erradas") p.set("erradas", "true");
    if (filtro === "favoritas") p.set("favoritas", "true");
    try {
      setErro(null);
      setLista(await api.get(`/questoes?${p}`));
    } catch (e) { setErro(e instanceof ApiError ? e.message : "Erro ao carregar."); }
  }, [disc, filtro, busca]);

  useEffect(() => { void carregar(); }, [carregar]);

  if (abertaId !== null) return <Resolver id={abertaId} aoVoltar={() => { setAbertaId(null); void carregar(); }} />;

  return (
    <>
      <h1>Questões</h1>
      <section className="cartao formulario">
        <label>Disciplina
          <select value={disc} onChange={(e) => setDisc(e.target.value)}>
            {DISCIPLINAS.map(([c, n]) => <option key={c} value={c}>{n}</option>)}
          </select>
        </label>
        <label>Mostrar
          <select value={filtro} onChange={(e) => setFiltro(e.target.value)}>
            <option value="">Todas</option>
            <option value="gabarito">Só com gabarito (corrigíveis)</option>
            <option value="inedita">Ainda não respondidas</option>
            <option value="erradas">Que errei por último</option>
            <option value="favoritas">Favoritas</option>
          </select>
        </label>
        <label>Buscar no texto
          <input value={busca} maxLength={100} onChange={(e) => setBusca(e.target.value)} />
        </label>
      </section>
      {erro && <p className="erro" role="alert">{erro}</p>}
      {lista && lista.total === 0 && (
        <p className="suave">Nenhuma questão. Importe provas na aba <strong>Provas</strong>.</p>
      )}
      {lista && lista.total > 0 && <p className="suave">{lista.total} questões (mostrando até 50).</p>}
      <ul className="lista-simples">
        {lista?.itens.map((q) => (
          <li key={q.id}>
            <button className="link" onClick={() => setAbertaId(q.id)}>
              {q.favorita ? "★ " : ""}{q.origem === "oficial" ? `VUNESP ${q.ano ?? ""} nº ${q.numero_original ?? "?"}` : "Gerada por IA"}
              {" · "}{q.disciplina_nome ?? "sem disciplina"}
              {!q.tem_gabarito && " · sem gabarito"}
            </button>
            <span className="suave">{q.enunciado}</span>
          </li>
        ))}
      </ul>
    </>
  );
}

function Resolver({ id, aoVoltar }: { id: number; aoVoltar: () => void }) {
  const [q, setQ] = useState<Questao | null>(null);
  const [escolha, setEscolha] = useState<string | null>(null);
  const [res, setRes] = useState<Resultado | null>(null);
  const [quadros, setQuadros] = useState<Quadro[] | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [inicio] = useState(() => Date.now());

  useEffect(() => { api.get<Questao>(`/questoes/${id}`).then(setQ).catch((e) => setMsg(e.message)); }, [id]);

  async function responder() {
    if (!escolha) return;
    setMsg(null);
    try {
      setRes(await api.post<Resultado>(`/questoes/${id}/responder`, {
        alternativa: escolha, tempo_segundos: Math.round((Date.now() - inicio) / 1000),
      }));
    } catch (e) { setMsg(e instanceof ApiError ? e.message : "Erro."); }
  }
  async function favoritar() {
    if (!q) return;
    const r = await api.put<{ favorita: boolean }>(`/questoes/${id}/favorita`, { favorita: !q.favorita });
    setQ({ ...q, favorita: r.favorita });
  }
  async function entender() {
    setMsg("Gerando explicação…");
    try {
      const r = await api.post<{ quadros: Quadro[] }>(`/questoes/${id}/quadrinhos`, {});
      setQuadros(r.quadros); setMsg(null);
    } catch (e) { setMsg(e instanceof ApiError ? e.message : "Erro."); }
  }

  if (!q) return <p className="suave">{msg ?? "Carregando…"}</p>;
  return (
    <>
      <button onClick={aoVoltar}>← Voltar</button>
      <h1>{q.origem === "oficial" ? `${q.documento ?? "Prova"} · nº ${q.numero_original}` : "Questão gerada por IA"}</h1>
      <p className="suave">{q.disciplina_nome}{q.origem !== "oficial" && " · conteúdo gerado por IA, confira nas fontes"}</p>
      {q.texto_apoio && <section className="cartao texto-apoio"><p>{q.texto_apoio}</p></section>}
      <p className="enunciado">{q.enunciado}</p>
      <div className="alternativas" role="radiogroup" aria-label="Alternativas">
        {q.alternativas.map((a) => {
          const certa = res && a.letra === res.gabarito;
          const errada = res && a.letra === escolha && !res.correta;
          return (
            <button key={a.letra} role="radio" aria-checked={escolha === a.letra} disabled={!!res || !q.tem_gabarito}
              className={`alt ${escolha === a.letra ? "marcado" : ""} ${certa ? "certa" : ""} ${errada ? "errada" : ""}`}
              onClick={() => setEscolha(a.letra)}>
              <strong>{a.letra}</strong> {a.texto}
            </button>
          );
        })}
      </div>
      {!q.tem_gabarito && <p className="aviso">Esta questão ainda não tem gabarito comprovado, então não pode ser corrigida. Veja a aba Provas.</p>}
      {!res && q.tem_gabarito && <button className="primario" disabled={!escolha} onClick={responder}>Responder</button>}
      {res && (
        <p className={res.correta ? "ok" : "erro"} role="status">
          {res.correta ? "Correto!" : `Errado. Gabarito oficial: ${res.gabarito}.`}
        </p>
      )}
      <div className="linha-botoes">
        <button onClick={favoritar}>{q.favorita ? "★ Favorita" : "☆ Favoritar"}</button>
        {res && <button onClick={entender}>ENTENDER ESTA QUESTÃO</button>}
      </div>
      {msg && <p className="suave" role="status">{msg}</p>}
      {quadros && (
        <section aria-label="Explicação em quadrinhos">
          <p className="suave">Explicação gerada por IA — confira normas e fatos nas fontes oficiais.</p>
          <div className="quadrinhos">
            {quadros.map((x, i) => (
              <figure key={i} className="quadro">
                <figcaption>{i + 1}. {x.titulo}</figcaption>
                <div className="cena">{x.cena}</div>
                <blockquote className="balao">{x.fala}</blockquote>
                {x.destaque && <mark>{x.destaque}</mark>}
              </figure>
            ))}
          </div>
        </section>
      )}
    </>
  );
}
