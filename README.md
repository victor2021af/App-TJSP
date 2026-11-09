# TJSP Aprovação

Plataforma pessoal de preparação para **Escrevente Técnico Judiciário — TJSP (Edital nº 02/2026, banca VUNESP)**.
PWA (React + TypeScript) com backend Python (FastAPI) e banco SQLite local. Funciona no computador e no
celular; os dados ficam no servidor, não no navegador.

> **Estado atual: Fases 1 a 6 escritas.** Veja "Verificação" para saber o que foi executado e o que ainda não foi.

## Como usar no Windows

Pré-requisitos: **Python 3.11+** (marque "Add to PATH") e **Node.js LTS**.

1. `instalar.bat` — cria o ambiente Python, instala dependências e compila a interface (precisa de internet).
2. `iniciar.bat` — abre o app em `http://127.0.0.1:8000`, **somente neste computador**.
3. O app abre direto, **sem senha** (padrão para uso pessoal local). Para exigir login, veja "Acesso e segurança".

Outros scripts: `testar.bat` (roda os testes), `backup.bat` (backup manual), `iniciar-com-senha.bat` (exige login),
`gerar-certificado.bat` e `iniciar-rede.bat` (celular na mesma rede — veja [docs/HTTPS-LOCAL.md](docs/HTTPS-LOCAL.md)).

Desenvolvimento (dois terminais): `cd backend && .venv\Scripts\python -m uvicorn app.main:app --reload` e
`cd frontend && npm run dev` (abre em `http://127.0.0.1:5173`, com proxy para a API).

## O que funciona (Fase 1 e início da 2)

| Recurso | Detalhe |
|---|---|
| Acesso | **Sem senha por padrão** (uso local). Login opcional com `TJSP_AUTH=on`: senha com scrypt, token guardado só como hash, bloqueio após 5 falhas em 5 min |
| Proteções sem senha | Só aceita acesso por `localhost` ou IP de rede privada (barra DNS rebinding) e exige JSON em pedidos que alteram dados (barra pedidos forjados por outras páginas) |
| Persistência real | SQLite em `backend/data/tjsp.db`, modo WAL, migrações versionadas (`backend/app/migrations`) |
| Estrutura do edital | Blocos, disciplinas e **todos os itens do Anexo VIII** carregados do edital (texto original preservado) |
| Conteúdo programático | Navegar por bloco/disciplina/assunto e marcar a situação (não iniciado → dominado) |
| Cronômetro de estudo | Pausar/retomar/finalizar; só conta tempo efetivo; o estado fica no servidor (sobrevive a fechar a aba) |
| Painel | Horas hoje/total, sequência, meta diária, conteúdo concluído, matérias prioritárias, sugestão do próximo assunto |
| Metas | Meta diária, disponibilidade semanal, data de início |
| Backup/restauração | Backup consistente (API do SQLite), automático a cada 24 h ao iniciar, restauração com cópia de segurança prévia |
| PWA | Manifest, ícones, service worker (só o "casco" do app; nunca guarda dados da API) |

Regras de honestidade do painel: sem dados, os valores aparecem como **"—"** ou zero; não há "probabilidade de
aprovação" inventada; a sugestão do próximo assunto é uma regra determinística (prioridade + ordem do edital) e
é rotulada como tal.

## Fases 3 a 6 (novas)

| Recurso | Detalhe |
|---|---|
| Importador de provas | `importar-provas.bat <pasta>`: 4 provas antigas → 400 questões com 5 alternativas, texto-base, disciplina por faixa; **sem gabarito** até vincular |
| Gabaritos | Guardados separados; só se aplicam à prova com texto de conferência e mesmo total (ver docs/FONTES.md) |
| Banco de questões | Filtros (disciplina, só corrigíveis, não respondidas, erradas, favoritas, busca), resolver, favoritar, histórico e estatísticas reais |
| Revisão espaçada | 1/7/15/30 dias após marcar "estudado"; <80% repete, <60% recomeça e marca "necessita reforço" |
| Simulado completo | 70 questões na distribuição do edital; gabarito só no final; mínimos de 50% dos Blocos I e II |
| Professor IA + quadrinhos | Contexto = desempenho real; quadrinhos só com gabarito comprovado; rotulado como IA (docs/IA.md) |
| Redações | Foto → correção por IA com o texto do edital; envio só com autorização; nota apenas estimada |
| Busca/URL | Google CSE (se configurado) e download restrito a domínios oficiais (docs/FONTES.md) |

## O que ainda não existe

Recorte/rotação de foto de redação (a imagem é enviada como está), gráficos semanais/mensais no painel, planejamento adaptativo
completo, "questões geradas por IA" (o campo e o rótulo existem; o gerador ainda não), perfis separados por pessoa e hospedagem na nuvem.

## Verificação — leia antes de confiar

Este código foi escrito num ambiente **sem acesso à internet para instalar pacotes**. O que foi e o que não foi
executado:

- ✅ **Executado e passando (testes sem servidor):** migrações, seed, restrições do banco, cronômetro, painel, autenticação,
  backup, **importador (também rodado nos 4 PDFs reais: 100 questões × 5 alternativas cada)**, gabaritos, banco de questões,
  revisão espaçada, simulados, camada de IA (com provedor falso), redação e validação de URLs.
- ⚠️ **Escrito, mas NÃO executado:** a camada HTTP (`app/main.py`, `app/routers/*`) — só teve a sintaxe verificada,
  pois o FastAPI não estava instalado. Os testes de API (`tests/test_api.py`) existem e **rodam na sua máquina**
  após `instalar.bat` (aqui foram ignorados).
- ⚠️ **APIs reais de IA e Google, e download por URL:** nunca chamadas (sem rede/chave aqui); testadas só com provedor falso.
- ⚠️ **Frontend:** sintaxe TypeScript verificada, mas **não compilado nem aberto num navegador** (Vite e tipos do
  React indisponíveis). Pode haver erros de tipo/layout no primeiro `npm run build`.
- ⚠️ **Scripts `.bat` e HTTPS no celular:** não testados (ambiente Linux).
- Versões em `requirements.txt` e `package.json` são faixas mínimas, não versões testadas em conjunto.

Primeiro passo recomendado: rodar `instalar.bat` e `testar.bat`. Se algo falhar, envie a mensagem de erro.

## Acesso e segurança (sem senha)

O login vem **desligado**. Isso significa que **quem conseguir abrir o endereço do app tem acesso total** (ver, alterar,
restaurar backups). Na prática:

- `iniciar.bat` (só neste PC, `127.0.0.1`): ninguém mais na rede alcança o app. Risco baixo.
- `iniciar-rede.bat` (celular, você e sua namorada): **qualquer aparelho na mesma rede Wi-Fi** pode abrir o app e mexer
  nos dados. Seguro o bastante numa rede doméstica com pessoas de confiança; **não use** em Wi-Fi público, de
  trabalho, faculdade ou hotspot de terceiros. Nunca faça redirecionamento de porta no roteador.
- Para voltar a exigir senha: use `iniciar-com-senha.bat` (só neste PC) ou `iniciar-rede-com-senha.bat` (celular);
  na primeira vez o app pede para criar o usuário. Se abrir o app pelo nome do computador em vez do IP, defina
  `TJSP_ALLOWED_HOSTS=nome-do-pc` antes de iniciar.
- **Os dois compartilham o mesmo histórico:** há um único banco de estudo. Se ela também for estudar para o concurso e
  vocês quiserem progresso separado, isso exige perfis por pessoa — diga se quer e eu planejo.

## Estrutura

```
tjsp-aprovacao/
├── backend/            API FastAPI, regras de negócio (services/), migrações SQL, testes
├── frontend/           React + TypeScript + Vite (PWA)
├── docs/               ARQUITETURA.md, HTTPS-LOCAL.md
└── *.bat               scripts de instalação e execução no Windows
```

Detalhes técnicos, modelo de dados, riscos e cronograma: [docs/ARQUITETURA.md](docs/ARQUITETURA.md).

## Privacidade

Nada é enviado a terceiros nesta fase: não há integração com IA ainda. Quando existir (Fases 4 e 5), as chaves de
API ficarão só no backend e o envio de imagens a provedores exigirá sua autorização explícita. A pasta
`backend/data/` (banco, backups, futuros uploads) e `certs/` estão no `.gitignore`.
