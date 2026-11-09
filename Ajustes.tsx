import { useCallback, useEffect, useState } from "react";
import { ApiError, api, type BackupInfo, type Configuracoes } from "../api";
import { tamanho } from "../format";

const DIAS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"];

export function Ajustes({ nome, comLogin, aoSair }: { nome: string; comLogin: boolean; aoSair: () => void }) {
  const [cfg, setCfg] = useState<Configuracoes | null>(null);
  const [meta, setMeta] = useState("");
  const [semana, setSemana] = useState<string[]>(Array(7).fill(""));
  const [inicio, setInicio] = useState("");
  const [backups, setBackups] = useState<BackupInfo[]>([]);
  const [enderecos, setEnderecos] = useState<string[]>([]);
  const [msg, setMsg] = useState<string | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  const carregar = useCallback(async () => {
    try {
      const [c, b, r] = await Promise.all([
        api.get<Configuracoes>("/configuracoes"),
        api.get<BackupInfo[]>("/backups"),
        api.get<{ enderecos_locais: string[] }>("/rede"),
      ]);
      setCfg(c);
      setMeta(c.meta_diaria_minutos?.toString() ?? "");
      setSemana((c.disponibilidade_semanal_minutos ?? Array(7).fill(null)).map((v) => (v === null ? "" : String(v))));
      setInicio(c.data_inicio_estudos ?? "");
      setBackups(b);
      setEnderecos(r.enderecos_locais);
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : "Erro ao carregar.");
    }
  }, []);

  useEffect(() => {
    void carregar();
  }, [carregar]);

  async function tentar(fn: () => Promise<void>, ok: string) {
    setErro(null);
    setMsg(null);
    try {
      await fn();
      setMsg(ok);
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : "Erro inesperado.");
    }
  }

  const salvarMetas = () =>
    tentar(async () => {
      const valores: Record<string, unknown> = {
        meta_diaria_minutos: meta === "" ? null : Number(meta),
        data_inicio_estudos: inicio === "" ? null : inicio,
        // A grade semanal só é enviada se todos os 7 dias estiverem preenchidos; vazia remove a configuração.
        disponibilidade_semanal_minutos: semana.every((v) => v === "") ? null : semana.map((v) => Number(v || 0)),
      };
      const nova = await api.put<Configuracoes>("/configuracoes", valores);
      setCfg(nova);
    }, "Configurações salvas.");

  const criarBackup = () =>
    tentar(async () => {
      await api.post("/backups");
      setBackups(await api.get<BackupInfo[]>("/backups"));
    }, "Backup criado.");

  const restaurar = (nomeBackup: string) => {
    const ok = window.confirm(
      `Restaurar "${nomeBackup}" substitui TODOS os dados atuais por este backup.\n` +
        "O estado atual será guardado antes como backup de segurança. Continuar?",
    );
    if (!ok) return;
    void tentar(async () => {
      await api.post(`/backups/${encodeURIComponent(nomeBackup)}/restaurar`, { confirmar: true });
      await carregar();
    }, "Backup restaurado. Se algo parecer desatualizado, saia e entre novamente.");
  };

  if (!cfg && !erro) return <p className="suave">Carregando…</p>;

  return (
    <>
      <h1>Ajustes</h1>
      {msg && <p className="ok" role="status">{msg}</p>}
      {erro && <p className="erro" role="alert">{erro}</p>}

      <section className="cartao formulario">
        <h2>Metas e disponibilidade</h2>
        <label>
          Meta diária (minutos)
          <input type="number" inputMode="numeric" min={0} max={1440} value={meta} onChange={(e) => setMeta(e.target.value)} />
        </label>
        <fieldset>
          <legend>Minutos disponíveis por dia da semana</legend>
          <div className="semana">
            {DIAS.map((d, i) => (
              <label key={d}>
                {d}
                <input
                  type="number" inputMode="numeric" min={0} max={1440} value={semana[i]}
                  onChange={(e) => setSemana((s) => s.map((v, j) => (j === i ? e.target.value : v)))}
                />
              </label>
            ))}
          </div>
        </fieldset>
        <label>
          Data de início dos estudos
          <input type="date" value={inicio} onChange={(e) => setInicio(e.target.value)} />
        </label>
        <button className="primario" onClick={salvarMetas}>Salvar</button>
      </section>

      <section className="cartao">
        <h2>Backup e restauração</h2>
        <p className="suave">
          Seus dados ficam no banco do servidor (não no navegador). Um backup automático é criado ao iniciar o servidor
          quando o último tem mais de 24 horas.
        </p>
        <button onClick={criarBackup}>Criar backup agora</button>
        {backups.length === 0 ? (
          <p className="suave">Nenhum backup ainda.</p>
        ) : (
          <ul className="lista-simples">
            {backups.map((b) => (
              <li key={b.nome}>
                <span>
                  {b.nome} <span className="suave">· {tamanho(b.bytes)}{b.automatico_de_seguranca ? " · segurança" : ""}</span>
                </span>
                <button onClick={() => restaurar(b.nome)}>Restaurar</button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="cartao">
        <h2>Usar no celular</h2>
        {enderecos.length === 0 ? (
          <p className="suave">Não foi possível detectar o endereço do computador na rede.</p>
        ) : (
          <p>Com o servidor iniciado em modo rede, abra no celular (mesma rede Wi-Fi): {enderecos.map((ip) => <code key={ip}> https://{ip}:8443 </code>)}</p>
        )}
        <p className="suave">Veja docs/HTTPS-LOCAL.md para instalar o certificado no celular e adicionar o app à tela inicial.</p>
      </section>

      {comLogin ? (
        <section className="cartao">
          <h2>Conta</h2>
          <p>Conectado como <strong>{nome}</strong>.</p>
          <button onClick={aoSair}>Sair</button>
        </section>
      ) : (
        <section className="cartao">
          <h2>Acesso</h2>
          <p className="suave">
            O login está desligado: quem abrir o endereço do app tem acesso total aos dados. Use somente em rede de casa.
            Para exigir senha, inicie o servidor com TJSP_AUTH=on (veja o README).
          </p>
        </section>
      )}
    </>
  );
}
