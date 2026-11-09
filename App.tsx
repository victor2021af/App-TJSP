import { useCallback, useEffect, useState } from "react";
import { api, guardarToken, lerToken } from "./api";
import { Acesso } from "./pages/Acesso";
import { Ajustes } from "./pages/Ajustes";
import { Conteudo } from "./pages/Conteudo";
import { Estudar, type Preset } from "./pages/Estudar";
import { Painel } from "./pages/Painel";
import { Professor } from "./pages/Professor";
import { Provas } from "./pages/Provas";
import { Questoes } from "./pages/Questoes";
import { Redacoes } from "./pages/Redacoes";
import { Revisoes } from "./pages/Revisoes";
import { Simulados } from "./pages/Simulados";

type Aba = "painel" | "estudar" | "questoes" | "simulados" | "revisoes" | "professor" | "redacoes" | "provas" | "conteudo" | "ajustes";
type Estado = "carregando" | "configurar" | "entrar" | "logado";

const ABAS: { id: Aba; rotulo: string; icone: string }[] = [
  { id: "painel", rotulo: "Painel", icone: "▦" },
  { id: "estudar", rotulo: "Estudar", icone: "⏱" },
  { id: "questoes", rotulo: "Questões", icone: "?" },
  { id: "simulados", rotulo: "Simulados", icone: "✔" },
  { id: "revisoes", rotulo: "Revisões", icone: "↻" },
  { id: "professor", rotulo: "Professor", icone: "✎" },
  { id: "redacoes", rotulo: "Redações", icone: "✐" },
  { id: "provas", rotulo: "Provas", icone: "▤" },
  { id: "conteudo", rotulo: "Conteúdo", icone: "☰" },
  { id: "ajustes", rotulo: "Ajustes", icone: "⚙" },
];

function abaDoHash(): Aba {
  const h = window.location.hash.replace("#", "") as Aba;
  return ABAS.some((a) => a.id === h) ? h : "painel";
}

export default function App() {
  const [estado, setEstado] = useState<Estado>("carregando");
  const [nome, setNome] = useState("");
  const [comLogin, setComLogin] = useState(false);
  const [aba, setAba] = useState<Aba>(abaDoHash);
  const [preset, setPreset] = useState<Preset | null>(null);

  const descobrirEstado = useCallback(async () => {
    try {
      const e = await api.get<{ configurado: boolean; auth_ativa: boolean }>("/auth/estado");
      if (!e.auth_ativa) {
        // Modo padrão (uso pessoal local): sem tela de senha.
        setComLogin(false);
        setEstado("logado");
        return;
      }
      setComLogin(true);
    } catch {
      setEstado("entrar");
      return;
    }
    try {
      if (lerToken()) {
        const eu = await api.get<{ nome: string }>("/auth/eu");
        setNome(eu.nome);
        setEstado("logado");
        return;
      }
    } catch {
      guardarToken(null);
    }
    try {
      const e = await api.get<{ configurado: boolean }>("/auth/estado");
      setEstado(e.configurado ? "entrar" : "configurar");
    } catch {
      setEstado("entrar");
    }
  }, []);

  useEffect(() => {
    void descobrirEstado();
    const aoExpirar = () => setEstado("entrar");
    window.addEventListener("tjsp:sessao-expirada", aoExpirar);
    return () => window.removeEventListener("tjsp:sessao-expirada", aoExpirar);
  }, [descobrirEstado]);

  useEffect(() => {
    const aoMudarHash = () => setAba(abaDoHash());
    window.addEventListener("hashchange", aoMudarHash);
    return () => window.removeEventListener("hashchange", aoMudarHash);
  }, []);

  function ir(destino: Aba, p: Preset | null = null) {
    setPreset(p);
    window.location.hash = destino;
    setAba(destino);
  }

  async function sair() {
    try {
      await api.post("/auth/sair");
    } catch {
      /* mesmo sem servidor, encerra a sessão localmente */
    }
    guardarToken(null);
    setEstado("entrar");
  }

  if (estado === "carregando") return <div className="centro">Carregando…</div>;

  if (estado !== "logado") {
    return (
      <Acesso
        modo={estado}
        aoEntrar={(n) => {
          setNome(n);
          setEstado("logado");
        }}
      />
    );
  }

  return (
    <div className="app">
      <nav className="menu" aria-label="Navegação principal">
        <div className="marca">TJSP Aprovação</div>
        {ABAS.map((a) => (
          <button
            key={a.id}
            className={`menu-item ${aba === a.id ? "ativo" : ""}`}
            aria-current={aba === a.id ? "page" : undefined}
            onClick={() => ir(a.id)}
          >
            <span aria-hidden="true">{a.icone}</span>
            <span>{a.rotulo}</span>
          </button>
        ))}
      </nav>
      <main className="conteudo">
        {aba === "painel" && <Painel nome={nome} aoEstudar={(p) => ir("estudar", p)} />}
        {aba === "estudar" && <Estudar preset={preset} />}
        {aba === "questoes" && <Questoes />}
        {aba === "simulados" && <Simulados />}
        {aba === "revisoes" && <Revisoes />}
        {aba === "professor" && <Professor />}
        {aba === "redacoes" && <Redacoes />}
        {aba === "provas" && <Provas />}
        {aba === "conteudo" && <Conteudo aoEstudar={(p) => ir("estudar", p)} />}
        {aba === "ajustes" && <Ajustes nome={nome} comLogin={comLogin} aoSair={sair} />}
      </main>
    </div>
  );
}
