-- 0002: banco de questões, tentativas, favoritas, revisões espaçadas, simulados e redações.
-- As telas e a importação chegam nas fases seguintes; o esquema já fica pronto para que o
-- painel e as estatísticas leiam tabelas reais desde a Fase 1 (hoje vazias).

CREATE TABLE documentos (
    id            INTEGER PRIMARY KEY,
    nome_arquivo  TEXT NOT NULL,
    tipo          TEXT NOT NULL CHECK (tipo IN ('edital','apostila','prova','outro')),
    banca         TEXT,
    ano           INTEGER,
    paginas       INTEGER,
    sha256        TEXT UNIQUE,
    importado_em  TEXT NOT NULL
);

CREATE TABLE questoes (
    id                    INTEGER PRIMARY KEY,
    origem                TEXT NOT NULL CHECK (origem IN ('oficial','ia','manual')),
    banca                 TEXT,
    ano                   INTEGER,
    documento_id          INTEGER REFERENCES documentos(id),
    pagina_origem         INTEGER,
    numero_original       INTEGER,
    disciplina_id         INTEGER REFERENCES disciplinas(id),
    assunto_id            INTEGER REFERENCES assuntos(id),
    subassunto            TEXT,
    dificuldade           TEXT CHECK (dificuldade IN ('basico','intermediario','avancado')),
    texto_apoio           TEXT,               -- texto-base compartilhado, quando houver
    enunciado             TEXT NOT NULL,
    gabarito              TEXT CHECK (gabarito IN ('A','B','C','D','E')),  -- NULL = não comprovado
    justificativa         TEXT,
    precisa_revisao_manual INTEGER NOT NULL DEFAULT 0 CHECK (precisa_revisao_manual IN (0,1)),
    motivo_revisao        TEXT,
    criada_em             TEXT NOT NULL,
    -- Questão do banco oficial nunca pode vir sem rastro da fonte.
    CHECK (origem <> 'oficial' OR documento_id IS NOT NULL)
);
CREATE INDEX idx_questoes_disciplina ON questoes(disciplina_id);
CREATE INDEX idx_questoes_assunto ON questoes(assunto_id);
CREATE INDEX idx_questoes_origem ON questoes(origem);

CREATE TABLE alternativas (
    questao_id  INTEGER NOT NULL REFERENCES questoes(id) ON DELETE CASCADE,
    letra       TEXT NOT NULL CHECK (letra IN ('A','B','C','D','E')),
    texto       TEXT NOT NULL,
    explicacao  TEXT,                          -- por que está certa/errada
    PRIMARY KEY (questao_id, letra)
);

CREATE TABLE simulados (
    id               INTEGER PRIMARY KEY,
    titulo           TEXT NOT NULL,
    tipo             TEXT NOT NULL CHECK (tipo IN ('completo','disciplina','assunto','personalizado')),
    somente_oficiais INTEGER NOT NULL DEFAULT 0 CHECK (somente_oficiais IN (0,1)),
    tempo_limite_seg INTEGER,
    iniciado_em      TEXT NOT NULL,
    finalizado_em    TEXT,
    segundos_usados  INTEGER
);

CREATE TABLE simulado_questoes (
    simulado_id  INTEGER NOT NULL REFERENCES simulados(id) ON DELETE CASCADE,
    questao_id   INTEGER NOT NULL REFERENCES questoes(id),
    posicao      INTEGER NOT NULL,
    PRIMARY KEY (simulado_id, questao_id)
);

CREATE TABLE tentativas (
    id                 INTEGER PRIMARY KEY,
    questao_id         INTEGER NOT NULL REFERENCES questoes(id),
    alternativa        TEXT NOT NULL CHECK (alternativa IN ('A','B','C','D','E')),
    correta            INTEGER NOT NULL CHECK (correta IN (0,1)),
    tempo_segundos     INTEGER CHECK (tempo_segundos >= 0),
    contexto           TEXT NOT NULL DEFAULT 'estudo' CHECK (contexto IN ('estudo','simulado','revisao')),
    simulado_id        INTEGER REFERENCES simulados(id),
    tipo_erro          TEXT CHECK (tipo_erro IN ('falta_conhecimento','interpretacao','desatencao',
                                                  'confusao_conceitos','calculo','regra','tempo')),
    respondida_em      TEXT NOT NULL
);
CREATE INDEX idx_tentativas_questao ON tentativas(questao_id);
CREATE INDEX idx_tentativas_data ON tentativas(respondida_em);

CREATE TABLE questoes_favoritas (
    questao_id  INTEGER PRIMARY KEY REFERENCES questoes(id) ON DELETE CASCADE,
    criada_em   TEXT NOT NULL
);

CREATE TABLE revisoes_agendadas (
    id           INTEGER PRIMARY KEY,
    assunto_id   INTEGER NOT NULL REFERENCES assuntos(id) ON DELETE CASCADE,
    etapa        INTEGER NOT NULL DEFAULT 0,     -- índice na lista de intervalos (24h, 7d, 15d, 30d)
    devida_em    TEXT NOT NULL,
    concluida_em TEXT,
    acerto_pct   INTEGER
);
CREATE INDEX idx_revisoes_devida ON revisoes_agendadas(devida_em) WHERE concluida_em IS NULL;

CREATE TABLE redacoes (
    id                INTEGER PRIMARY KEY,
    tema              TEXT,
    arquivo_imagem    TEXT,                     -- caminho relativo dentro de uploads/
    texto_transcrito  TEXT,
    provedor_ia       TEXT,
    relatorio_json    TEXT,
    nota_estimada     REAL,                     -- estimativa do app, NÃO é nota oficial da VUNESP
    criada_em         TEXT NOT NULL
);
