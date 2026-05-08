# Migração CrewAI → Paperclip AI

**Data:** 2026-05-08
**Branch:** PlannerAgent
**Status:** Aprovado pelo usuário

---

## Objetivo

Substituir todo o uso de CrewAI pelo Paperclip AI, migrando o servidor Python para TypeScript/Node.js e registrando cada agente como um worker HTTP no Paperclip. Ferramentas complexas de mídia (Flux, Hunyuan3D, Playwright, Stable Diffusion) são excluídas e serão reconfiguradas futuramente.

---

## O que muda

### Deletado
- `server/` — todos os 30+ arquivos Python
- `agents.py`, `tasks.py`, `main.py`, `planner_main.py` (root)
- `supabase/Usersv27mecrewai-studio/` — CrewAI Studio
- Ferramentas excluídas: Flux, Hunyuan3D, Playwright, Stable Diffusion, Vision, Awwwards, Browser Capture

### Mantido sem alteração
- `src/` — jogo TypeScript/PixiJS
- `assets/` — assets do jogo
- `vite.config.ts`, `index.html`
- Supabase (banco de mensagens do jogo)
- Integrações: Trello, GitHub, Vault/Obsidian

### Adicionado
- Paperclip AI server (orquestrador central)
- `game-server/` — novo backend Express TypeScript
- `workers/` — um worker por tipo de agente
- `paperclip/company.json` — org chart da empresa

---

## Arquitetura

```
[Trello]
    │ novo card detectado
    ▼
[Planner Worker]
    │ cria tasks no Paperclip
    ▼
[Paperclip Server]  ←── UI de configuração (browser)
    │ distribui tasks via heartbeat
    ├──→ [Copywriter Worker]
    ├──→ [Designer Worker]
    ├──→ [Dev Worker]  (Claude Code CLI nativo)
    ├──→ [QA Worker]
    └──→ [DevOps Worker] ──→ GitHub

[Jogo Frontend (PixiJS)] ──→ [Game Server (Express/TS)]
                                    │
                                    ├─ /api/chat/:agentId
                                    ├─ /api/agents
                                    ├─ /api/tasks
                                    ├─ /api/vault
                                    └─ SSE (stream)
```

**3 processos rodando em paralelo:**
1. `paperclip` — servidor Paperclip (porta padrão)
2. `game-server` — Express TypeScript (porta 8000)
3. `workers/` — um processo HTTP por agente, registrados no Paperclip

---

## Estrutura de Pastas

```
be-game/
├── src/                        ← jogo PixiJS (não toca)
├── assets/                     ← assets do jogo (não toca)
├── paperclip/
│   └── company.json            ← org chart: Black Elephant
├── game-server/
│   ├── index.ts                ← Express + SSE
│   ├── routes/
│   │   ├── chat.ts             ← POST /api/chat/:agentId
│   │   ├── agents.ts           ← GET /api/agents
│   │   ├── tasks.ts            ← GET /api/tasks
│   │   └── vault.ts            ← GET|POST /api/vault/knowledge
│   ├── lib/
│   │   ├── paperclip.ts        ← cliente HTTP do Paperclip API
│   │   ├── trello.ts           ← Trello API
│   │   ├── github.ts           ← GitHub API
│   │   ├── vault.ts            ← leitura .md Obsidian
│   │   └── supabase.ts         ← Supabase client
│   └── tsconfig.json
├── workers/
│   ├── planner.ts              ← poll Trello → cria tasks Paperclip
│   ├── copywriter.ts           ← escreve copy via LLM
│   ├── designer.ts             ← guia visual via LLM
│   ├── dev.ts                  ← spawn Claude Code CLI
│   ├── qa.ts                   ← revisa código via LLM
│   ├── devops.ts               ← git init + push GitHub
│   ├── secretario.ts           ← NPC: status do pipeline
│   └── bibliotecario.ts        ← NPC: busca vault
├── vite.config.ts              ← sem alteração
└── package.json                ← adiciona Express, Anthropic SDK
```

---

## Fluxos Principais

### Pipeline Trello → Site

```
1. planner.ts     poll a cada 60s → novo card detectado
2. planner.ts     cria Project + Tasks no Paperclip via API
3. Paperclip      distribui via heartbeat para cada worker
4. copywriter.ts  recebe task → chama LLM → salva no vault
5. designer.ts    recebe task → chama LLM → salva no vault
6. dev.ts         recebe task → spawn Claude Code CLI
7. qa.ts          recebe task → analisa arquivos → veredicto
8. devops.ts      recebe task → git init + push GitHub
9. planner.ts     fecha card no Trello (move p/ Done)
```

### Chat NPC (jogo)

```
1. Jogador clica no NPC
2. POST /api/chat/secretario → game-server
3. game-server cria task urgente no Paperclip
4. secretario.ts recebe heartbeat → chama LLM → responde
5. game-server retorna resposta ao frontend (polling ou webhook)
```

---

## Decisões Técnicas

| Decisão | Escolha | Motivo |
|---|---|---|
| Framework backend | Express.js (TypeScript) | Simples, já usado no ecossistema |
| Workers | Servidores HTTP Express mínimos | Paperclip chama via POST /task |
| LLM | Configurado pelo usuário no painel Paperclip | Usuário fará configuração manual |
| Vault | Leitura direta dos `.md` do Obsidian | Sem Qdrant por enquanto |
| Banco de mensagens | Supabase (mantido) | Sem alteração |
| PyAutoGUI | Não migrado | Mantido em crew_sites_institucionais |

---

## Fora de Escopo

- Ferramentas de mídia: Flux, Hunyuan3D, Playwright, Stable Diffusion, Vision
- PyAutoGUI (mantido separado em crew_sites_institucionais)
- Qdrant / embeddings semânticos
- crewai-studio UI

---

## Próximos Passos

Invocar `writing-plans` para criar o plano de implementação detalhado com tasks e ordem de execução.
