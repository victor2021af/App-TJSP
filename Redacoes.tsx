import { useEffect, useState } from "react";
import { ApiError, api } from "../api";

interface Item { id: number; tema: string | null; status: string; nota_estimada: number | null; criada_em: string }
interface Rel {
  transcricao?: string; criterios?: Record<string, { parecer?: string; problemas?: string[] }>;
  situacoes_de_nota_zero?: { item: string; ocorre: boolean; justificativa: string }[];
  pontos_a_melhorar?: string[]; proximo_exercicio?: string;
}
interface Det { id: number; tema: string | null; status: string; nota_estimada: number | null; aviso: string | null; relatorio: Rel | null }

function paraBase64(f: File): Promise<string> {
  return new Promise((ok, falha) => {
    const r = new FileReader();
    r.onload = () => ok(String(r.result).split(",")[1] ?? "");
    r.onerror = () => falha(new Error("Não consegui ler a imagem."));
    r.readAsDataURL(f);
  });
}

export function Redacoes() {
  const [lista, setLista] = useState<Item[]>([]);
  const [tema, setTema] = useState("");
  const [arquivo, setArquivo] = useState<File | null>(null);
  const [autorizo, setAutorizo] = useState(false);
  const [det, setDet] = useState<Det | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const carregar = () => api.get<Item[]>("/redacoes").then(setLista).catch(() => undefined);
  useEffect(() => { void carregar(); }, []);

  async function enviar() {
    if (!arquivo) return;
    setOcupado(true); setMsg(null);
    try {
      const { redacao_id } = await api.post<{ redacao_id: number }>("/redacoes", { imagem_base64: await paraBase64(arquivo), tema: tema || null });
      setMsg("Foto salva neste computador. Nada foi enviado à IA ainda.");
      if (autorizo) {
        setMsg("Enviando para correção…");
        await api.post(`/redacoes/${redacao_id}/corrigir`, { autorizo_envio: true });
      }
      setDet(await api.get<Det>(`/redacoes/${redacao_id}`));
      setArquivo(null); setAutorizo(false);
      await carregar();
    } catch (e) { setMsg(e instanceof ApiError ? e.message : (e as Error).message); }
    setOcupado(false);
  }

  async function corrigirExistente(id: number) {
    if (!window.confirm("Enviar a imagem desta redação ao provedor de IA para correção?")) return;
    try {
      await api.post(`/redacoes/${id}/corrigir`, { autorizo_envio: true });
      setDet(await api.get<Det>(`/redacoes/${id}`)); await carregar();
    } catch (e) { setMsg(e instanceof ApiError ? e.message : "Erro."); }
  }
  async function copiarPrompt() {
    const r = await api.get<{ prompt: string }>(`/redacoes/prompt?tema=${encodeURIComponent(tema)}`);
    try { await navigator.clipboard.writeText(r.prompt); setMsg("Prompt copiado: cole em outro chat de IA e anexe a foto lá."); }
    catch { setMsg("Não consegui copiar automaticamente."); }
  }

  if (det) return <Detalhe d={det} aoVoltar={() => setDet(null)} aoCorrigir={() => corrigirExistente(det.id)} />;

  return (
    <>
      <h1>Minhas redações</h1>
      <p className="suave">Edital: dissertativo-argumentativa, nota de 0 a 40, aprovação com 24 pontos ou mais. A nota deste app é só uma <strong>estimativa de IA</strong>, não a nota da VUNESP.</p>
      <section className="cartao formulario">
        <label>Tema / proposta (opcional)<textarea rows={2} maxLength={500} value={tema} onChange={(e) => setTema(e.target.value)} /></label>
        <label>Foto da redação
          <input type="file" accept="image/jpeg,image/png,image/webp" capture="environment" onChange={(e) => setArquivo(e.target.files?.[0] ?? null)} />
        </label>
        <label className="check">
          <input type="checkbox" checked={autorizo} onChange={(e) => setAutorizo(e.target.checked)} style={{ width: "auto", minHeight: 0 }} />
          {" "}Autorizo enviar esta imagem ao provedor de IA configurado para correção. (Sem marcar, a foto fica só neste computador.)
        </label>
        <button className="primario" disabled={!arquivo || ocupado} onClick={enviar}>{autorizo ? "Salvar e corrigir" : "Salvar foto"}</button>{" "}
        <button onClick={copiarPrompt}>Copiar prompt para usar em outra IA</button>
        {msg && <p role="status" className="suave">{msg}</p>}
      </section>
      <h2>Histórico</h2>
      {lista.length === 0 && <p className="suave">Nenhuma redação ainda.</p>}
      <ul className="lista-simples">
        {lista.map((r) => (
          <li key={r.id}>
            <button className="link" onClick={async () => setDet(await api.get<Det>(`/redacoes/${r.id}`))}>{r.tema || `Redação ${r.id}`}</button>
            <span className="suave">{new Date(r.criada_em).toLocaleDateString("pt-BR")} · {r.status}{r.nota_estimada !== null && ` · estimativa ${r.nota_estimada}/40`}</span>
          </li>
        ))}
      </ul>
    </>
  );
}

function Detalhe({ d, aoVoltar, aoCorrigir }: { d: Det; aoVoltar: () => void; aoCorrigir: () => void }) {
  const r = d.relatorio;
  return (
    <>
      <button onClick={aoVoltar}>← Voltar</button>
      <h1>{d.tema || `Redação ${d.id}`}</h1>
      <img src={`/api/redacoes/${d.id}/imagem`} alt="Foto da redação" style={{ maxWidth: "100%", borderRadius: 8 }} />
      {d.status !== "corrigida" || !r ? (
        <p><button className="primario" onClick={aoCorrigir}>Corrigir com IA (envia a imagem)</button></p>
      ) : (
        <>
          <p className="aviso">{d.aviso} <strong>Estimativa: {d.nota_estimada ?? "—"}/40.</strong> Gerado por IA.</p>
          {Object.entries(r.criterios ?? {}).map(([k, c]) => (
            <section className="cartao" key={k}><h2>{k}</h2><p>{c.parecer}</p>
              <ul>{(c.problemas ?? []).map((p, i) => <li key={i}>{p}</li>)}</ul></section>
          ))}
          {(r.situacoes_de_nota_zero ?? []).filter((s) => s.ocorre).map((s) => (
            <p className="erro" key={s.item}>Nota zero (item {s.item}): {s.justificativa}</p>
          ))}
          <h2>Pontos a melhorar</h2>
          <ul>{(r.pontos_a_melhorar ?? []).map((p, i) => <li key={i}>{p}</li>)}</ul>
          {r.proximo_exercicio && <p><strong>Próximo exercício:</strong> {r.proximo_exercicio}</p>}
          {r.transcricao && <details><summary>Transcrição lida pela IA (confira!)</summary><p>{r.transcricao}</p></details>}
        </>
      )}
    </>
  );
}
