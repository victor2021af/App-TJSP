-- 0001: núcleo — usuário, sessões de login, configurações, estrutura do edital,
-- progresso por assunto, sessões de estudo e trilha de auditoria.
-- Datas/horas: texto ISO-8601 em UTC (YYYY-MM-DDTHH:MM:SSZ).

CREATE TABLE usuarios (
    id          INTEGER PRIMARY KEY,
    nome        TEXT    NOT NULL,
    senha_hash  TEXT    NOT NULL,
    criado_em   TEXT    NOT NULL
);

CREATE TABLE sessoes_login (
    id          INTEGER PRIMARY KEY,
    usuario_id  INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    token_hash  TEXT    NOT NULL UNIQUE,   -- só o hash do token é guardado
    criado_em   TEXT    NOT NULL,
    expira_em   TEXT    NOT NULL
);
CREATE INDEX idx_sessoes_login_expira ON sessoes_login(expira_em);

CREATE TABLE configuracoes (
    chave         TEXT PRIMARY KEY,
    valor         TEXT NOT NULL,
    atualizado_em TEXT NOT NULL
);

-- Estrutura oficial (Edital TJSP nº 02/2026) -------------------------------------------

CREATE TABLE blocos (
    id                  INTEGER PRIMARY KEY,
    codigo              TEXT    NOT NULL UNIQUE,
    nome                TEXT    NOT NULL,
    ordem               INTEGER NOT NULL,
    num_questoes        INTEGER NOT NULL,
    eliminatorio        INTEGER NOT NULL CHECK (eliminatorio IN (0, 1)),
    minimo_acertos_pct  INTEGER            -- NULL quando o bloco é só classificatório
);

CREATE TABLE disciplinas (
    id               INTEGER PRIMARY KEY,
    bloco_id         INTEGER NOT NULL REFERENCES blocos(id),
    codigo           TEXT    NOT NULL UNIQUE,
    nome             TEXT    NOT NULL,
    ordem            INTEGER NOT NULL,
    num_questoes     INTEGER,             -- NULL quando o edital não divide o bloco por disciplina
    prioridade       INTEGER NOT NULL DEFAULT 2 CHECK (prioridade BETWEEN 1 AND 3),
    descricao_edital TEXT
);

-- Assuntos e subassuntos (parent_id). `texto_edital` guarda o texto original do Anexo VIII.
CREATE TABLE assuntos (
    id             INTEGER PRIMARY KEY,
    disciplina_id  INTEGER NOT NULL REFERENCES disciplinas(id),
    parent_id      INTEGER REFERENCES assuntos(id),
    ref_edital     TEXT,
    titulo         TEXT    NOT NULL,
    texto_edital   TEXT,
    ordem          INTEGER NOT NULL
);
CREATE INDEX idx_assuntos_disciplina ON assuntos(disciplina_id);
CREATE UNIQUE INDEX idx_assuntos_unico ON assuntos(disciplina_id, ordem, titulo);

CREATE TABLE progresso_assunto (
    assunto_id     INTEGER PRIMARY KEY REFERENCES assuntos(id) ON DELETE CASCADE,
    status         TEXT NOT NULL DEFAULT 'nao_iniciado'
                   CHECK (status IN ('nao_iniciado','em_andamento','estudado',
                                     'em_revisao','dominado','necessita_reforco')),
    atualizado_em  TEXT NOT NULL
);

-- Estudo ---------------------------------------------------------------------------------

CREATE TABLE sessoes_estudo (
    id                  INTEGER PRIMARY KEY,
    disciplina_id       INTEGER REFERENCES disciplinas(id),
    assunto_id          INTEGER REFERENCES assuntos(id),
    objetivo            TEXT,
    status              TEXT NOT NULL CHECK (status IN ('em_andamento','pausada','concluida')),
    iniciada_em         TEXT NOT NULL,
    em_execucao_desde   TEXT,                    -- preenchido só enquanto o cronômetro corre
    segundos_acumulados INTEGER NOT NULL DEFAULT 0 CHECK (segundos_acumulados >= 0),
    finalizada_em       TEXT,
    objetivo_cumprido   INTEGER CHECK (objetivo_cumprido IN (0, 1)),
    observacao          TEXT
);
CREATE INDEX idx_sessoes_estudo_status ON sessoes_estudo(status);
CREATE INDEX idx_sessoes_estudo_fim ON sessoes_estudo(finalizada_em);
-- No máximo uma sessão aberta (em andamento ou pausada) por vez.
CREATE UNIQUE INDEX idx_sessao_unica_aberta ON sessoes_estudo((1)) WHERE status <> 'concluida';

-- Registro de alterações importantes ----------------------------------------------------

CREATE TABLE auditoria (
    id          INTEGER PRIMARY KEY,
    quando      TEXT NOT NULL,
    usuario_id  INTEGER REFERENCES usuarios(id) ON DELETE SET NULL,
    acao        TEXT NOT NULL,
    entidade    TEXT,
    entidade_id TEXT,
    detalhes    TEXT
);
CREATE INDEX idx_auditoria_quando ON auditoria(quando);
