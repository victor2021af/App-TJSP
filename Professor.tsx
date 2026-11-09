import { useEffect, useRef, useState } from "react";
import { ApiError, api } from "../api";

interface Msg { papel: "aluno" | "professor"; texto: string }

export function Professor() {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [texto, setTexto] = useState("");
  const [ia, setIa] = useState<{ configurada: boolean; motivo?: string } | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const fim = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.get<{ configurada: boolean; motivo?: string }>("/ia/estado").then(setIa).catch(() => undefined);
    api.get<Msg[]>("/professor/historico").then(setMsgs).catch(() => undefined);
  }, []);
  useEffect(() => { fim.current?.scrollIntoView({ block: "end" }); }, [msgs]);

  async function enviar() {
    const p = texto.trim();
    if (!p || enviando) return;
    setEnviando(true); setErro(null);
    setMsgs((m) => [...m, { papel: "aluno", texto: p }]); setTexto("");
    try {
      const r = await api.post<{ resposta: string }>("/professor/conversar", { pergunta: p });
      setMsgs((m) => [...m, { papel: "professor", texto: r.resposta }]);
    } catch (e) { setErro(e instanceof ApiError ? e.message : "Erro."); }
    setEnviando(false);
  }

  return (
    <>
      <h1>Meu Professor IA</h1>
      <p className="suave">Respostas geradas por IA. Ele conhece seu desempenho real registrado aqui (questões, erros, revisões). Confira normas nas fontes oficiais.</p>
      {ia && !ia.configurada && <p className="aviso">{ia.motivo}</p>}
      <div className="chat" aria-live="polite">
        {msgs.map((m, i) => <div key={i} className={`bolha ${m.papel}`}>{m.texto}</div>)}
        <div ref={fim} />
      </div>
      {erro && <p className="erro" role="alert">{erro}</p>}
      <label>Sua pergunta
        <textarea rows={3} maxLength={4000} value={texto} onChange={(e) => setTexto(e.target.value)} />
      </label>
      <button className="primario" disabled={enviando || !texto.trim()} onClick={enviar}>{enviando ? "Pensando…" : "Perguntar"}</button>
    </>
  );
}
