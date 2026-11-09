-- 0004: conversas com o Professor IA, explicações em quadrinhos (cache) e correções de redação.
CREATE TABLE conversas_professor (
    id         INTEGER PRIMARY KEY,
    papel      TEXT NOT NULL CHECK (papel IN ('aluno','professor')),
    texto      TEXT NOT NULL,
    provedor   TEXT,
    criado_em  TEXT NOT NULL
);

CREATE TABLE explicacoes_questao (
    questao_id  INTEGER PRIMARY KEY REFERENCES questoes(id) ON DELETE CASCADE,
    quadros_json TEXT NOT NULL,
    provedor    TEXT NOT NULL,
    gerada_por_ia INTEGER NOT NULL DEFAULT 1 CHECK (gerada_por_ia = 1),   -- sempre rotulada como IA
    criada_em   TEXT NOT NULL
);

ALTER TABLE redacoes ADD COLUMN autorizou_envio INTEGER NOT NULL DEFAULT 0;
ALTER TABLE redacoes ADD COLUMN status TEXT NOT NULL DEFAULT 'pendente' CHECK (status IN ('pendente','corrigida','erro'));
ALTER TABLE redacoes ADD COLUMN aviso TEXT;
