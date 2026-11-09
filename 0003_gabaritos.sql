-- 0003: gabaritos oficiais guardados SEPARADOS das questões.
-- Um gabarito só vira resposta de questão quando é vinculado a uma prova (e versão) conferida.
CREATE TABLE gabaritos (
    id            INTEGER PRIMARY KEY,
    descricao     TEXT NOT NULL,
    data_prova    TEXT,
    versao        TEXT NOT NULL DEFAULT '1',
    total         INTEGER NOT NULL,
    origem        TEXT,                       -- arquivo ou URL de onde veio
    sha256        TEXT,
    importado_em  TEXT NOT NULL,
    documento_id  INTEGER REFERENCES documentos(id),   -- prova a que foi aplicado (NULL = não vinculado)
    aplicado_em   TEXT,
    conferencia   TEXT,                       -- como o vínculo foi conferido (texto livre, obrigatório ao aplicar)
    UNIQUE (sha256, versao)
);

CREATE TABLE gabarito_respostas (
    gabarito_id  INTEGER NOT NULL REFERENCES gabaritos(id) ON DELETE CASCADE,
    numero       INTEGER NOT NULL,
    letra        TEXT NOT NULL CHECK (letra IN ('A','B','C','D','E')),
    PRIMARY KEY (gabarito_id, numero)
);

ALTER TABLE questoes ADD COLUMN gabarito_id INTEGER REFERENCES gabaritos(id);
