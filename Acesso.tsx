import { useState, type FormEvent } from "react";
import { ApiError, api, guardarToken } from "../api";

interface Props {
  modo: "configurar" | "entrar";
  aoEntrar: (nome: string) => void;
}

export function Acesso({ modo, aoEntrar }: Props) {
  const [nome, setNome] = useState("");
  const [senha, setSenha] = useState("");
  const [confirma, setConfirma] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const primeiroAcesso = modo === "configurar";

  async function enviar(e: FormEvent) {
    e.preventDefault();
    setErro(null);
    if (primeiroAcesso && senha !== confirma) {
      setErro("As senhas não coincidem.");
      return;
    }
    setEnviando(true);
    try {
      const r = await api.post<{ token: string; nome: string }>(
        primeiroAcesso ? "/auth/configurar" : "/auth/entrar",
        { nome, senha },
      );
      guardarToken(r.token);
      aoEntrar(r.nome);
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Erro inesperado.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="centro">
      <form className="cartao acesso" onSubmit={enviar}>
        <h1>TJSP Aprovação</h1>
        <p className="suave">
          {primeiroAcesso
            ? "Primeiro acesso: crie o usuário que protege os seus dados de estudo."
            : "Entre para continuar de onde parou."}
        </p>
        <label>
          Nome
          <input value={nome} onChange={(e) => setNome(e.target.value)} autoComplete="username" required maxLength={80} />
        </label>
        <label>
          Senha {primeiroAcesso && <span className="suave">(mínimo 8 caracteres)</span>}
          <input
            type="password"
            value={senha}
            onChange={(e) => setSenha(e.target.value)}
            autoComplete={primeiroAcesso ? "new-password" : "current-password"}
            required
            minLength={primeiroAcesso ? 8 : 1}
          />
        </label>
        {primeiroAcesso && (
          <label>
            Repita a senha
            <input type="password" value={confirma} onChange={(e) => setConfirma(e.target.value)} autoComplete="new-password" required />
          </label>
        )}
        {erro && <p className="erro" role="alert">{erro}</p>}
        <button className="primario" disabled={enviando}>
          {enviando ? "Aguarde…" : primeiroAcesso ? "Criar e entrar" : "Entrar"}
        </button>
      </form>
    </div>
  );
}
