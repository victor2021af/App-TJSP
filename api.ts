// Cliente da API. O token de login fica no navegador; todos os DADOS de estudo ficam no servidor.

const CHAVE_TOKEN = "tjsp.token";

export function lerToken(): string | null {
  try {
    return localStorage.getItem(CHAVE_TOKEN);
  } catch {
    return null;
  }
}

export function guardarToken(token: string | null): void {
  try {
    if (token) localStorage.setItem(CHAVE_TOKEN, token);
    else localStorage.removeItem(CHAVE_TOKEN);
  } catch {
    /* modo privado: o login simplesmente não persiste */
  }
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, mensagem: string) {
    super(mensagem);
    this.status = status;
  }
}

async function chamar<T>(metodo: string, caminho: string, corpo?: unknown): Promise<T> {
  const cabecalhos: Record<string, string> = {};
  const token = lerToken();
  if (token) cabecalhos["Authorization"] = `Bearer ${token}`;
  if (corpo !== undefined) cabecalhos["Content-Type"] = "application/json";

  let resposta: Response;
  try {
    resposta = await fetch(`/api${caminho}`, {
      method: metodo,
      headers: cabecalhos,
      body: corpo === undefined ? undefined : JSON.stringify(corpo),
    });
  } catch {
    throw new ApiError(0, "Não foi possível falar com o servidor. Verifique se ele está em execução.");
  }

  if (resposta.status === 204) return undefined as T;
  const texto = await resposta.text();
  let dados: unknown = null;
  try {
    dados = texto ? JSON.parse(texto) : null;
  } catch {
    /* resposta não-JSON */
  }

  if (!resposta.ok) {
    if (resposta.status === 401 && token) {
      guardarToken(null);
      window.dispatchEvent(new Event("tjsp:sessao-expirada"));
    }
    const detalhe =
      dados && typeof dados === "object" && "detalhe" in dados ? (dados as { detalhe: unknown }).detalhe : null;
    throw new ApiError(resposta.status, typeof detalhe === "string" ? detalhe : `Erro ${resposta.status}`);
  }
  return dados as T;
}

export const api = {
  get: <T,>(caminho: string) => chamar<T>("GET", caminho),
  post: <T,>(caminho: string, corpo?: unknown) => chamar<T>("POST", caminho, corpo ?? {}),
  put: <T,>(caminho: string, corpo: unknown) => chamar<T>("PUT", caminho, corpo),
};

// ---- tipos (espelham as respostas do backend) -------------------------------------------------

export type StatusAssunto =
  | "nao_iniciado"
  | "em_andamento"
  | "estudado"
  | "em_revisao"
  | "dominado"
  | "necessita_reforco";

export const ROTULO_STATUS: Record<StatusAssunto, string> = {
  nao_iniciado: "Não iniciado",
  em_andamento: "Em andamento",
  estudado: "Estudado",
  em_revisao: "Em revisão",
  dominado: "Dominado",
  necessita_reforco: "Necessita reforço",
};

export interface Disciplina {
  id: number;
  codigo: string;
  nome: string;
  num_questoes: number | null;
  prioridade: number;
  descricao_edital: string | null;
  assuntos_total: number;
  status_contagem: Record<StatusAssunto, number>;
}

export interface Bloco {
  id: number;
  codigo: string;
  nome: string;
  num_questoes: number;
  eliminatorio: boolean;
  minimo_acertos_pct: number | null;
  disciplinas: Disciplina[];
}

export interface Assunto {
  id: number;
  ref_edital: string | null;
  titulo: string;
  texto_edital: string | null;
  status: StatusAssunto;
}

export interface SessaoEstudo {
  id: number;
  disciplina_id: number | null;
  assunto_id: number | null;
  objetivo: string | null;
  status: "em_andamento" | "pausada" | "concluida";
  iniciada_em: string;
  segundos_decorridos: number;
  cronometro_correndo: boolean;
}

export interface SessaoHistorico {
  id: number;
  finalizada_em: string;
  segundos_acumulados: number;
  objetivo: string | null;
  objetivo_cumprido: number | null;
  disciplina_nome: string | null;
  assunto_titulo: string | null;
}

export interface Painel {
  estudo: {
    total_segundos: number;
    hoje_segundos: number;
    sequencia_dias: number;
    por_disciplina: { disciplina_id: number | null; nome: string; segundos: number }[];
    meta_diaria_minutos: number | null;
    meta_diaria_cumprida_pct: number | null;
  };
  questoes: {
    respondidas: number;
    acertos: number;
    erros: number;
    acerto_pct: number | null;
    tempo_medio_segundos: number | null;
  };
  conteudo: { total_assuntos: number; por_status: Partial<Record<StatusAssunto, number>>; concluido_pct: number | null };
  indicador_preparo: {
    descricao: string;
    conteudo_concluido_pct: number | null;
    meta_do_dia_pct: number | null;
    acerto_pct: number | null;
  };
  ultimos_assuntos: { id: number; finalizada_em: string; segundos_acumulados: number; disciplina: string | null; assunto: string }[];
  proximas_revisoes: { id: number; assunto: string; devida_em: string }[];
  materias_prioritarias: { disciplina_id: number; nome: string; prioridade: number; concluido_pct: number }[];
  sugestao_automatica: { assunto_id: number; titulo: string; disciplina_id: number; disciplina: string; motivo: string } | null;
}

export interface Configuracoes {
  meta_diaria_minutos: number | null;
  disponibilidade_semanal_minutos: number[] | null;
  data_inicio_estudos: string | null;
}

export interface BackupInfo {
  nome: string;
  bytes: number;
  automatico_de_seguranca: boolean;
}
