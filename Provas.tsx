import { useEffect, useState } from "react";
import { ApiError, api } from "../api";

interface Doc { id: number; nome_arquivo: string; ano: number | null; questoes: number; com_gabarito: number }
interface Gab { id: number; descricao: string; data_prova: string | null; versao: string; total: number; documento_id: number | null; prova: string | null; conferencia: string | null }
interface Achado { titulo: string; url: string; trecho: string; importavel: boolean }

export function Provas() {
  const [docs, setDocs] = useState<Doc[]>([]);
  const [gabs, setGabs] = useState<Gab[]>([]);
  const [msg, setMsg] = useState<string | null>(null);
  const [consulta, setConsulta] = useState("gabarito oficial escrevente técnico judiciário TJSP VUNESP");
  const [achados, setAchados] = useState<Achado[]>([]);
  const [url, setUrl] = useState("");
  const [tipo, setTipo] = useState("gabarito");
  const [desc, setDesc] = useState("");
  const [total, setTotal] = useState("70");
  const [vinc, setVinc] = useState<Record<number, { doc: string; conf: string }>>({});

  const carregar = async () => {
    setDocs(await api.get<Doc[]>("/documentos")); setGabs(await api.get<Gab[]>("/gabaritos"));
  };
  useEffect(() => { void carregar().catch(() => undefined); }, []);

  const tentar = async (fn: () => Promise<unknown>, ok: string) => {
    setMsg(null);
    try { await fn(); setMsg(ok); await carregar(); } catch (e) { setMsg(e instanceof ApiError ? e.message : "Erro."); }
  };

  return (
    <>
      <h1>Provas e gabaritos</h1>
      <p className="suave">Provas importadas ficam <strong>sem gabarito</strong> até você vincular um gabarito oficial conferido. Questões sem gabarito não são corrigidas.</p>
      {msg && <p role="status" className="aviso">{msg}</p>}

      <h2>Provas importadas</h2>
      {docs.length === 0 && <p className="suave">Nenhuma. Rode <code>importar-provas.bat</code> apontando para a pasta com seus PDFs, ou importe por endereço abaixo.</p>}
      <ul className="lista-simples">
        {docs.map((d) => <li key={d.id}><span>{d.nome_arquivo}</span><span className="suave">{d.questoes} questões · {d.com_gabarito} com gabarito</span></li>)}
      </ul>

      <h2>Gabaritos guardados</h2>
      <ul className="lista-simples">
        {gabs.map((g) => (
          <li key={g.id}>
            <span>{g.descricao} · versão {g.versao} · {g.total} respostas<br />
              {g.documento_id ? <span className="ok">Aplicado a: {g.prova}. Conferência: {g.conferencia}</span> : <span className="suave">Não vinculado</span>}</span>
            {!g.documento_id && (
              <span className="formulario">
                <select value={vinc[g.id]?.doc ?? ""} onChange={(e) => setVinc({ ...vinc, [g.id]: { doc: e.target.value, conf: vinc[g.id]?.conf ?? "" } })}>
                  <option value="">Prova…</option>
                  {docs.filter((d) => d.questoes === g.total && d.com_gabarito === 0).map((d) => <option key={d.id} value={d.id}>{d.nome_arquivo}</option>)}
                </select>
                <input placeholder="Como você conferiu o pareamento? (mín. 10 caracteres)" value={vinc[g.id]?.conf ?? ""}
                  onChange={(e) => setVinc({ ...vinc, [g.id]: { doc: vinc[g.id]?.doc ?? "", conf: e.target.value } })} />
                <button disabled={!vinc[g.id]?.doc || (vinc[g.id]?.conf ?? "").length < 10}
                  onClick={() => tentar(() => api.post(`/gabaritos/${g.id}/aplicar`, { documento_id: Number(vinc[g.id].doc), conferencia: vinc[g.id].conf }), "Gabarito aplicado.")}>Aplicar</button>
              </span>
            )}
          </li>
        ))}
      </ul>

      <section className="cartao formulario">
        <h2>Buscar na web (Google)</h2>
        <p className="suave">Precisa de GOOGLE_CSE_KEY e GOOGLE_CSE_CX (docs/FONTES.md). Só domínios oficiais são importáveis.</p>
        <label>Busca<input value={consulta} maxLength={200} onChange={(e) => setConsulta(e.target.value)} /></label>
        <button onClick={() => tentar(async () => setAchados(await api.post<Achado[]>("/fontes/buscar", { consulta })), "Busca concluída.")}>Buscar</button>
        <ul className="lista-simples">
          {achados.map((a) => (
            <li key={a.url}><span><a href={a.url} target="_blank" rel="noreferrer noopener">{a.titulo}</a><br /><span className="suave">{a.trecho}</span></span>
              {a.importavel ? <button onClick={() => setUrl(a.url)}>Usar</button> : <span className="suave">domínio não permitido</span>}</li>
          ))}
        </ul>
      </section>

      <section className="cartao formulario">
        <h2>Importar PDF por endereço</h2>
        <label>Endereço (https)<input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://www.tjsp.jus.br/…pdf" /></label>
        <label>Tipo<select value={tipo} onChange={(e) => setTipo(e.target.value)}><option value="gabarito">Gabarito</option><option value="prova">Prova</option></select></label>
        <label>Descrição<input value={desc} maxLength={200} onChange={(e) => setDesc(e.target.value)} placeholder="Ex.: Gabarito TJSP dez/2025" /></label>
        {tipo === "gabarito" && <label>Nº de questões esperado<input type="number" min={1} max={200} value={total} onChange={(e) => setTotal(e.target.value)} /></label>}
        <button className="primario" disabled={!url || desc.length < 3}
          onClick={() => tentar(() => api.post("/fontes/importar-url", { url, tipo, descricao: desc, total_questoes: Number(total) }), "Importado.")}>Importar</button>
      </section>
    </>
  );
}
