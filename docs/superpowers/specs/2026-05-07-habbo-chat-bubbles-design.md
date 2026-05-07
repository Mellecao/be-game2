# Habbo-style Chat Bubbles + Secretário + Multi-Chat Windows

**Data:** 2026-05-07
**Autor:** brainstorming session com guilherme@blackelephant.com.br
**Estado:** design aprovado, aguardando review do user antes do plano de implementação

## 1. Contexto e motivação

O sistema atual de chat in-game tem 3 problemas:

1. **Visual fraco:** texto cinza com transparência flutuando acima dos NPCs (componente `whisperLabel` em `src/game/NPC.ts`). Sem distinção visual de tipos de mensagem, sem identificação clara de quem fala.
2. **Single chat window com bug:** `src/ui/ChatPanel.ts` aceita só 1 janela aberta por vez E compartilha histórico DOM entre agentes — abrir o chat de outro agente mostra a auto-mensagem do anterior.
3. **Sem voz pro player:** não há atalho ou input pra o jogador interagir com o pipeline.

Este spec substitui tudo isso por:

- Bolhas estilo Habbo Hotel moderno (gradiente dourado, avatar redondo, nome em negrito) para mensagens normais; bolhas cinza-translúcidas para "thinking" (whisper).
- 3 tipos de bolha (`say`, `whisper`, `player`) com regras de posicionamento, persistência e TTL diferentes.
- Multi-chat windows flutuantes draggable, uma por agente, sem compartilhar estado.
- Tecla **T** abre input que sempre conversa com **Secretário** (NPC novo, reativo).
- Click no **Bibliotecário** (NPC novo) abre chat com input. Demais agentes: chat read-only com histórico.
- Mensagens persistidas em SQLite (`agent_messages`).
- Handoff entre agentes gera mensagem natural via LLM ("Pesquisa pronta, passando 5 refs pro Copy").

## 2. Decisões de arquitetura

| Decisão | Escolha | Razão |
|---|---|---|
| Visual do balão | Habbo moderno (gradiente dourado, sem cauda) | Mais limpo em mundo isométrico, menos trabalho de z-ordering |
| Fonte do handoff | LLM-gen (DeepSeek v4 Flash) | Frases naturais por projeto vs templado robotizado |
| Multi-chat layout | Janelas flutuantes draggable | Imersivo (estilo Habbo), permite ver 2 conversas lado a lado |
| Persistência | SQLite `agent_messages` | Sobrevive reload e restart; suporta queries por agente/projeto/tempo |
| Quem o player conversa | Secretário (T) + Bibliotecário (click). Outros agentes: read-only | Mantém pipeline focado; player tem 2 "atendentes" com visão global |
| Secretário | Reativo apenas (responde quando perguntado) | Sem custo de tokens em loop; mais previsível |
| LLM do Secretário/Bibliotecário | `llm` global (DeepSeek v4 Flash via OpenRouter) | Já configurado; rápido; barato |
| Whisper persistence | Persiste até agente terminar | Comportamento "..." indica que está pensando |
| Say persistence | TTL dinâmico 2-8s, scrolla pra cima | Padrão Habbo — várias mensagens visíveis simultaneamente |
| Per-agente bubble stack | Stack local por NPC (sem fila global) | Cada NPC é "ilha" independente — n NPCs falando ao mesmo tempo |

## 3. Tipos de bolha

3 tipos, cada um com regra própria:

| Tipo | Visual | Posição | Persistência | Origem |
|---|---|---|---|---|
| **whisper** | Pill cinza-claro semi-transparente, sem nome de agente, max 5 linhas | Logo acima da cabeça, **fica parado** numa slot único | Substitui conteúdo conforme novos chunks; some quando agente termina | `llm_chunk` SSE (já existente) com buffer agregado |
| **say** | Pill dourado gradient (`#fbbf24 → #f59e0b`), avatar redondo + nome em negrito + texto | Acima do whisper; **sobe** com novas msgs (push the stack up) | TTL dinâmico 2-8s (`min(2000 + len*60, 8000)`), fade-out 300ms | LLM-gen no fim de cada step do agente (handoff) |
| **player** | Visualmente idêntico ao `say` mas avatar do Player + nome "Você" (kind tagueado pra storage/SSE, não pra render) | Acima do Player, sobe normal | TTL dinâmico | Tecla T → input → Enter |

Cada NPC tem `bubbleStack: SpeechBubble[]` (LIFO local) + `whisperSlot: SpeechBubble | null` (slot único). O whisper fica `WHISPER_LOWER` (16px) abaixo da pilha de `say` — say sempre acima.

Truncamento do whisper: max 5 linhas (~150 chars). Acima disso, `…` no início, mantém os últimos chars.

## 4. Secretário (novo agente NPC)

### 4.1 Backend

**`create_secretario()` em `server/agents.py`:**
- Role: "Atendente do Player"
- Goal: "Responder dúvidas sobre status do pipeline, atividades atuais e histórico de execução. Conversar de forma direta e objetiva, sem rodeio."
- Backstory: "Você é o secretário da Black Elephant. Tem visão completa do que está acontecendo no pipeline. Responde em português brasileiro, em 1-3 frases."
- Tools: `get_pipeline_status`, `get_active_tasks`, `get_agent_history` (3 tools novas)
- LLM: `llm` global (DeepSeek v4 Flash)
- `allow_delegation=False`

**Endpoint novo `POST /api/chat/secretario`** (em `server/api.py`):
- Body: `{message: str}`
- Response: `{reply: str}`
- Cria Crew de 1 agente + Task com a pergunta como description, kickoff, retorna output.
- Grava `record(slug='global', agent_id='secretario', type='reply', text=output)` antes de retornar.

**3 tools novas em `server/agent_messages_tools.py`:**

```python
class GetPipelineStatusTool(BaseTool):
    name = "get_pipeline_status"
    # retorna {card_atual, slug, step, status_label, started_at}

class GetActiveTasksTool(BaseTool):
    name = "get_active_tasks"
    # le _tasks do planner_loop, retorna lista de tasks ativas

class GetAgentHistoryTool(BaseTool):
    name = "get_agent_history"
    # input: agent_id, optional limit. Retorna ultimas N msgs daquele agente
```

**Sem participação no pipeline:** `_run_pipeline` ignora ele. Não emite chunks proativos.

### 4.2 Frontend (NPC no jogo)

Adicionar em `AGENT_SEED` (`server/api.py`):

```python
{"id": "secretario", "display_name": "Secretário", "role": "Atendente do Player",
 "goal": "Responder duvidas sobre o pipeline", "backstory": "...",
 "col": 0.5, "row": 0.5, "sprite_char": 4}
```

NPC fica num canto (não anda, não tem path). Aparência: terno/roupa formal (sprite_char escolhido pelo dev).

`_AGENT_DISPLAY` adiciona `"secretario": "Secretário"`.

## 5. Bibliotecário (NPC já existe como conceito, vira NPC visível)

**Nota de escopo:** o módulo `server/librarian.py` é uma camada de hooks (após research / dev / deploy etc.) que escreve no vault — NÃO é um Agent CrewAI. Esta seção cria um Agent CrewAI NOVO chamado "bibliotecario" que conversa com o player; eles compartilham só o `agent_id` e a metáfora. Os hooks do `librarian.py` continuam funcionando como antes.

`agent_id="bibliotecario"` já é usado em `server/librarian.py` (como `agent_id` em log events e frontmatter de notas). Adicionar entrada no `AGENT_SEED`:

```python
{"id": "bibliotecario", "display_name": "Bibliotecário", "role": "Curador do Vault",
 "goal": "Buscar contexto no vault e responder perguntas", "backstory": "...",
 "col": 9.5, "row": 0.5, "sprite_char": 5}
```

Posicionado no canto oposto ao Secretário.

**Endpoint novo `POST /api/chat/bibliotecario`** (similar ao Secretário, mas tools = `obsidian_vault_search`, `vault_browse`).

**Acesso:** click do player no NPC abre `ChatWindow` com input habilitado.

## 6. Persistência: SQLite `agent_messages`

### 6.1 Schema

Novo arquivo `server/db.py`:

```python
import sqlite3
from pathlib import Path

DB_PATH = Path(os.environ.get("AGENT_DB_PATH", "agent_messages.db"))

def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_schema() -> None:
    with get_conn() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS agent_messages (
              id          INTEGER PRIMARY KEY AUTOINCREMENT,
              slug        TEXT NOT NULL,
              agent_id    TEXT NOT NULL,
              type        TEXT NOT NULL,
              text        TEXT NOT NULL,
              ts          REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_am_agent ON agent_messages(agent_id, ts DESC);
            CREATE INDEX IF NOT EXISTS idx_am_slug  ON agent_messages(slug, ts DESC);
        """)
```

`init_schema()` chamado uma vez no startup do api.

### 6.2 Helpers

Novo arquivo `server/agent_messages.py`:

```python
def record(slug: str, agent_id: str, type: str, text: str) -> int:
    """Insert + emite SSE 'agent_message'. Retorna id."""

def history(agent_id: str, limit: int = 200) -> list[dict]:
    """Ultimas N msgs daquele agente, ordem cronologica asc."""

def recent(slug: str, since_ts: float, limit: int = 100) -> list[dict]:
    """Msgs do projeto desde timestamp."""
```

`record()` faz 2 coisas: insert no SQLite + `event_bus.emit("agent_message", {agent_id, type, text, ts, slug})` pro SSE.

### 6.3 Quando gravar

| Tipo | Quando | Onde |
|---|---|---|
| `whisper` | A cada N chunks (debounce 500ms) ou ao fim do step. Não chunk-a-chunk (poluiria DB) | `_on_llm_chunk` em `planner_loop.py` agrega buffer; flusha em `step_callback` ou no debounce |
| `say` | Após cada agent finalizar step (handoff gerado por LLM) | `step_callback` do Crew → `generate_handoff()` → `record()` |
| `player` | Player envia via T | Endpoint `/api/chat/secretario` antes de chamar LLM |
| `reply` | Secretário/Bibliotecário responde | Endpoint após Crew kickoff |

Tamanho estimado: ~500 msgs por projeto típico × 50 projetos = 25K rows. SQLite folgado.

Sem retenção automática nesta fase. Função `purge_older_than(days)` fica como comando admin futuro.

## 7. Handoffs LLM-generated

### 7.1 Função

Novo arquivo `server/handoff.py`:

```python
from functools import lru_cache

def generate_handoff(agent_id: str, agent_name: str, what_was_done: str, next_agent: str | None) -> str:
    """Gera mensagem curta de transicao via LLM. Cacheia por hash do input."""
    return _generate_cached(agent_id, agent_name, what_was_done[:200], next_agent or "")

@lru_cache(maxsize=128)
def _generate_cached(agent_id: str, agent_name: str, what_summary: str, next_agent: str) -> str:
    from .agents import llm
    prompt = (
        f"Voce e o {agent_name}. Acabou de entregar: {what_summary}.\n"
        f"Proximo agente: {next_agent or '(fim do pipeline)'}.\n"
        f"Em 1 frase <= 120 caracteres, em portugues coloquial, anuncie o que entregou "
        f"e pra quem passa. Sem meta-comentario, sem aspas."
    )
    try:
        out = llm.call(messages=[{"role": "user", "content": prompt}]).strip()
        return out[:140]
    except Exception:
        return _fallback(agent_name, next_agent)


def _fallback(agent_name: str, next_agent: str | None) -> str:
    return f"{agent_name} terminou. Passando pro {next_agent}." if next_agent else f"{agent_name} terminou."
```

### 7.2 Integração no pipeline

Em `server/planner_loop.py`, adicionar callback ao Crew:

```python
def _on_agent_step(step_output, agent_id: str, next_agent: str | None, slug: str):
    summary = str(step_output)[:200]
    text = generate_handoff(agent_id, AGENT_DISPLAY[agent_id], summary, next_agent)
    agent_messages.record(slug, agent_id, "say", text)
```

Plugado via `step_callback=lambda x: _on_agent_step(x, ...)` no `Crew(...)`.

### 7.3 Pontos de handoff

10 transições por pipeline máximo:
- Researcher → Copywriter
- Copywriter → Designer
- Designer → Image Artist
- Image Artist → 3D Artist (só se há `convert_to_3d`)
- 3D Artist → Designer Reviewer
- Designer Reviewer → Dev (último handoff do Crew Criativo)
- Dev → QA-Código
- QA-Código → QA-Visual (se aprovado)
- QA-Visual → DevOps (se aprovado) OU → Dev (se reprovado, com fix prompt)
- DevOps → Planner (closing)

Custos: ~50 tokens in + 30 out × 10 = ~800 tokens/pipeline. Negligível.

## 8. Renderização das bolhas (Pixi.js)

### 8.1 `src/game/SpeechBubble.ts` (novo)

Container Pixi com 3 variantes (`'say' | 'whisper' | 'player'`):

```ts
class SpeechBubble extends Container {
  constructor(
    text: string,
    kind: 'say' | 'whisper' | 'player',
    opts: { agentName?: string; agentAvatar?: Texture; ttl?: number }
  )

  // children:
  // - Graphics (rounded rect + gradient/border)
  // - Sprite (avatar redondo, masked)
  // - Text (nome bold + ":")
  // - Text (corpo)

  // exposes:
  height: number;       // medido após criar
  fadeOut(durationMs: number): Promise<void>;
}
```

**Variante `say`:**
- Fundo: gradiente `#fbbf24 → #f59e0b` (Mesh com 2 cores ou Graphics com 2 quads stackados)
- Borda: 2px branco interno + 1px `#92400e` externo
- Border-radius: 14px
- Padding: 8px
- Drop shadow leve (Pixi `DropShadowFilter`)
- Avatar: 24px círculo (máscara circular)
- Nome: bold, branco, 13px
- Texto: branco, 13px
- Largura máxima: 320px, `breakWords: true`

**Variante `whisper`:**
- Fundo: `#f3f4f6` alpha 0.85
- Borda: `#9ca3af` 1px tracejada (Graphics path manual com séries de `lineTo`/`moveTo` curtos)
- Sem avatar, sem nome
- Texto: `#374151`, 12px italic
- Padding: 6px
- Largura máxima: 240px, max 5 linhas (truncamento se ultrapassar)

**Variante `player`:**
- Idêntico a `say` mas avatar do Player + nome "Você"

### 8.2 `src/game/BubbleStack.ts` (novo)

Gerencia stack `say` + slot `whisper` por NPC:

```ts
const BASE_OFFSET = 40;   // px acima da cabeça
const GAP = 6;            // px entre bubbles na pilha
const WHISPER_LOWER = 16; // px abaixo da pilha de say

class BubbleStack {
  private stack: SpeechBubble[] = [];   // bubbles 'say' empilhados
  private whisperSlot: SpeechBubble | null = null;
  private container: Container;

  constructor(private npc: NPC) {
    this.container = new Container();
    npc.addChild(this.container);
  }

  pushSay(text: string, agentName: string, agentAvatar: Texture, ttl?: number): void {
    const bubble = new SpeechBubble(text, 'say', { agentName, agentAvatar, ttl });
    this.container.addChild(bubble);
    bubble.y = -BASE_OFFSET;

    // empurra existentes pra cima
    for (const existing of this.stack) {
      gsap.to(existing, {
        y: existing.y - (bubble.height + GAP),
        duration: 0.15,
        ease: 'power2.out',
      });
    }
    this.stack.push(bubble);

    // se whisper estiver ativo, agente terminou de pensar — limpa
    if (this.whisperSlot) this.clearWhisper();

    // re-posiciona whisper se ainda existe
    this.repositionWhisper();

    // agenda destroy
    const computedTtl = ttl ?? Math.min(2000 + text.length * 60, 8000);
    setTimeout(() => this.removeBubble(bubble), computedTtl);
  }

  setWhisper(text: string, agentName: string): void {
    if (this.whisperSlot) {
      this.whisperSlot.updateText(text);  // método novo em SpeechBubble
    } else {
      this.whisperSlot = new SpeechBubble(text, 'whisper', { agentName });
      this.container.addChild(this.whisperSlot);
    }
    this.repositionWhisper();
  }

  clearWhisper(): void {
    if (this.whisperSlot) {
      this.whisperSlot.fadeOut(200).then(() => {
        this.whisperSlot?.destroy();
        this.whisperSlot = null;
      });
    }
  }

  private repositionWhisper(): void {
    if (!this.whisperSlot) return;
    let stackBottom = -BASE_OFFSET;
    for (const b of this.stack) stackBottom = Math.min(stackBottom, b.y);
    this.whisperSlot.y = stackBottom + WHISPER_LOWER + this.whisperSlot.height;
  }

  private removeBubble(bubble: SpeechBubble): void {
    bubble.fadeOut(300).then(() => {
      bubble.destroy();
      this.stack = this.stack.filter(b => b !== bubble);
    });
  }

  destroy(): void {
    this.container.destroy({ children: true });
  }
}
```

### 8.3 Refactor `src/game/NPC.ts`

- **Remover:** `whisperLabel` (Pixi Text gray) e `setWhisperChunk` (acumulador 80 chars).
- **Adicionar:** `this.bubbles = new BubbleStack(this)` no constructor.
- **API pública:**
  - `npc.bubbles.setWhisper(text, agentName)`
  - `npc.bubbles.pushSay(text, agentName, avatarTexture)`
  - `npc.bubbles.clearWhisper()`

### 8.4 Z-index isométrico

`BubbleStack.container` é child do NPC Container. Inherits Y-sort do NPC. NPCs na frente da cena → bubbles na frente automaticamente. Sem trabalho extra de z-ordering.

## 9. Multi-chat windows flutuantes

### 9.1 `src/ui/ChatWindow.ts` (novo, substitui `ChatPanel.ts`)

HTMLElement absoluto, draggable, criado dinamicamente:

```html
<div class="chat-window" data-agent-id="researcher" style="left:200px;top:120px;z-index:1100">
  <div class="chat-header">
    <img class="chat-avatar" src="..." />
    <span class="chat-title">Researcher</span>
    <button class="chat-close" aria-label="Fechar">×</button>
  </div>
  <div class="chat-body">
    <div class="msg msg-whisper">[19:32] Procurando refs no awwwards…</div>
    <div class="msg msg-say"><b>Researcher:</b> Pesquisa pronta, 5 refs.</div>
  </div>
  <div class="chat-input-area"><!-- só pra secretario/bibliotecario -->
    <input type="text" placeholder="Pergunte..." maxlength="500" />
  </div>
</div>
```

Comportamentos:
- Drag: mousedown no header → captura offset, mousemove (em `document`) atualiza `left/top`, mouseup solta. Refs bound a document durante drag pra não perder se mouse sair.
- Close: × destrói DOM, remove do registry, salva posição em `localStorage["chat:agent_id:pos"]`.
- Click no body: traz pra frente (z-index += 1).
- Mensagens novas (via SSE): append em `chat-body`, scroll automático pro fim se já estava no fim.

Input area presente APENAS se `agent_id ∈ {secretario, bibliotecario}`. Submit (Enter) → `POST /api/chat/{id}` com `{message}`.

### 9.2 `src/ui/ChatWindowManager.ts` (novo)

Singleton global:

```ts
class ChatWindowManager {
  private windows = new Map<string, ChatWindow>();
  private nextZ = 1100;

  open(agentId: string): ChatWindow {
    const existing = this.windows.get(agentId);
    if (existing) {
      this.bringToFront(agentId);
      return existing;
    }
    const win = new ChatWindow(agentId);
    win.loadHistory();  // GET /api/agents/{id}/messages
    win.setPosition(this.computeStaggerPosition());
    this.windows.set(agentId, win);
    return win;
  }

  close(agentId: string): void { /* destroys, saves pos */ }
  bringToFront(agentId: string): void { /* z-index = nextZ++ */ }
  appendMessage(agentId: string, msg: AgentMessage): void { /* if open, append */ }

  private computeStaggerPosition(): { left: number; top: number } {
    const stored = localStorage.getItem(`chat:${agentId}:pos`);
    if (stored) return JSON.parse(stored);
    const count = this.windows.size;
    return { left: 80 + count * 30, top: 200 + count * 30 };
  }
}
```

### 9.3 Bug fix da mensagem compartilhada

O problema atual ("auto-mensagem do agente A aparece quando abro chat do agente B") some naturalmente: cada `ChatWindow` carrega seu próprio histórico via `GET /api/agents/{id}/messages` ao abrir. Não há estado DOM compartilhado.

### 9.4 CSS novo: `src/ui/chat-windows.css`

Estilos das janelas + bolhas + input (linkar em `index.html`).

```css
.chat-window {
  position: fixed;
  width: 360px; max-height: 480px;
  background: #1f2937; color: white;
  border-radius: 8px;
  box-shadow: 0 8px 24px rgba(0,0,0,0.4);
  font-family: system-ui, -apple-system, sans-serif;
  font-size: 13px;
  display: flex; flex-direction: column;
}

.chat-header {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 12px;
  background: linear-gradient(180deg, #fbbf24, #f59e0b);
  border-radius: 8px 8px 0 0;
  cursor: move;
}

.chat-avatar { width: 24px; height: 24px; border-radius: 50%; }
.chat-title  { flex: 1; font-weight: bold; color: #422006; }
.chat-close  { background: transparent; border: 0; color: #422006; font-size: 18px; cursor: pointer; }

.chat-body {
  flex: 1; overflow-y: auto;
  padding: 12px; min-height: 120px;
  display: flex; flex-direction: column; gap: 6px;
}

.msg-whisper { color: #9ca3af; font-style: italic; font-size: 12px; }
.msg-say     { color: white; }
.msg-player  { color: #fbbf24; }
.msg-reply   { color: #93c5fd; }

.chat-input-area { padding: 8px 12px; border-top: 1px solid #374151; }
.chat-input-area input {
  width: 100%; background: #111827; color: white; border: 1px solid #374151;
  border-radius: 4px; padding: 6px 8px; font-size: 13px; outline: none;
}
.chat-input-area input:focus { border-color: #fbbf24; }
```

## 10. Input do player (tecla T)

### 10.1 `src/ui/PlayerChatInput.ts` (novo)

```html
<div id="player-chat-input" class="hidden">
  <input type="text" placeholder="Pergunte ao Secretário..." maxlength="500" />
</div>
```

CSS bottom-left fixed, fundo escuro semi-transparente, borda dourada.

### 10.2 Comportamento

- **Tecla T:**
  - Se input fechado E player NÃO está digitando em outro lugar → abre + foco automático.
  - Se input aberto → fecha (toggle).
- **Enter** com input focado:
  - `POST /api/chat/secretario` com `{message: input.value}`.
  - **Imediato:** mostra bubble `kind: 'player'` acima do Player.
  - **Imediato:** mostra bubble `kind: 'whisper'` acima do Secretário NPC com texto "..." (placeholder).
  - Limpa input e fecha.
- **Esc** com input focado: fecha sem enviar.
- **W/A/S/D bloqueados** enquanto qualquer input do chat tem foco. `Player.bindInput` checa `document.activeElement.tagName === 'INPUT'`.

### 10.3 Resposta

Endpoint `/api/chat/secretario` retorna `{reply: text}` após Crew kickoff (~2-5s). Internamente:
1. `record(slug='global', agent_id='secretario', type='reply', text=reply)` antes de retornar.
2. `record()` emite SSE `agent_message`.
3. Frontend recebe → `BubbleStack` do Secretário troca whisper "..." por bubble `kind: 'say'` real.
4. Mesma msg aparece em `ChatWindow` do Secretário se aberta.

### 10.4 Erros

- Backend offline / 5xx: bubble do Secretário vira `kind: 'whisper'` com texto `"(erro de conexão)"` por 3s, depois some.
- Mensagem vazia: não envia.
- Timeout > 30s: aborta, whisper vira erro.

## 11. Endpoints e wiring

### 11.1 Endpoints novos

| Verbo + Path | Body | Response | Quem grava |
|---|---|---|---|
| `POST /api/chat/secretario` | `{message: str}` | `{reply: str}` | grava `player` antes do call e `reply` depois |
| `POST /api/chat/bibliotecario` | `{message: str}` | `{reply: str}` | idem |
| `GET /api/agents/{id}/messages?limit=200` | — | `{messages: [{type, text, ts, slug}]}` | — (read) |

### 11.2 Endpoint genérico antigo

`POST /api/chat` (genérico atual, usado por `ChatPanel.ts`) fica deprecated após rollout dos 2 específicos. Removido em fase de cleanup quando confirmado que nada mais consome. `ChatPanel.ts` é deletado.

### 11.3 SSE event types novos

Em `server/event_bus.py` (lista existente apenas amplia):
- `agent_message` — emitido por `record()`. Payload: `{slug, agent_id, type, text, ts}`.

## 12. Fluxo completo de uma interação

### 12.1 Pipeline rodando — handoff

```
1. Researcher termina trabalho dentro do Crew Criativo
2. CrewAI step_callback dispara → planner_loop._on_agent_step(output, "researcher", "copywriter", slug)
3. handoff.generate_handoff("researcher", "Researcher", "Pesquisa de 5 refs", "Copywriter")
   → LLM gera "Pesquisa pronta, 5 refs do Frankenstein, passando pro Copy"
4. agent_messages.record(slug, "researcher", "say", text)
5. record() insere SQLite + event_bus.emit("agent_message", payload)
6. Frontend SSE recebe → AgentToast.handleAgentMessage(payload)
7. AgentToast → ChatWindowManager.appendMessage("researcher", payload) (se janela aberta)
8. AgentToast → npc("researcher").bubbles.pushSay(text, "Researcher", avatar)
9. Bubble 'say' renderizado, scroll up das anteriores, TTL ~6s, fade-out
```

### 12.2 Player aperta T

```
1. Player aperta T → PlayerChatInput.toggle() abre input bottom-left
2. Player digita "qual o status do site institucional?" + Enter
3. Frontend imediatamente:
   - player.bubbles.pushSay("qual o status...", "Você", playerAvatar) → bolha 'player'
   - secretarioNpc.bubbles.setWhisper("...", "Secretário") → bolha whisper "..."
4. Frontend POST /api/chat/secretario {message}
5. Backend:
   - record(slug='global', agent_id='player', type='player', text=message)
   - Crew(secretario_agent + Task("user perguntou: ...")).kickoff()
   - Secretário usa get_pipeline_status / get_active_tasks pra responder
   - reply = "O site institucional está no step Designer, slug 'rose-beauty'. Já tem 5 refs e copy aprovada."
   - record(slug='global', agent_id='secretario', type='reply', text=reply)
   - return {reply}
6. record() emite SSE agent_message → frontend
7. AgentToast → secretarioNpc.bubbles.clearWhisper() (some o "...")
8. AgentToast → secretarioNpc.bubbles.pushSay(reply, "Secretário", secretarioAvatar)
9. Player vê bolha 'say' do Secretário com a resposta
10. Se ChatWindow do Secretário estiver aberta, msg também aparece lá
```

### 12.3 Player clica em agente (ex: Researcher)

```
1. NPC click handler em Game.ts → ChatWindowManager.open("researcher")
2. ChatWindow é criado, loadHistory() faz GET /api/agents/researcher/messages
3. Backend: agent_messages.history("researcher", limit=200)
4. Renderiza todas msgs no .chat-body
5. Não tem input area (só read-only)
6. Janela fica draggable, x fecha, click no body traz pra frente
```

## 13. Map de arquivos

### Novos

```
server/
  db.py                             # SQLite conn + init_schema
  agent_messages.py                 # record() / history() / recent()
  agent_messages_tools.py           # GetPipelineStatusTool, GetActiveTasksTool, GetAgentHistoryTool
  handoff.py                        # generate_handoff() com lru_cache

src/game/
  SpeechBubble.ts                   # Container Pixi com 3 variantes
  BubbleStack.ts                    # gerencia stack 'say' + slot 'whisper' por NPC

src/ui/
  ChatWindow.ts                     # janela flutuante draggable
  ChatWindowManager.ts              # registry singleton, multi-instance
  PlayerChatInput.ts                # input bottom-left ativado por T
  chat-windows.css                  # CSS das janelas + bolhas + input
```

### Modificados

```
server/
  agents.py                         # +create_secretario, +create_bibliotecario_agent
  api.py                            # +POST /api/chat/secretario, +POST /api/chat/bibliotecario, +GET /api/agents/{id}/messages, AGENT_SEED ganha secretario+bibliotecario
  planner_loop.py                   # _on_llm_chunk com debounce → flush whisper. step_callback chama generate_handoff + record('say')

src/game/
  NPC.ts                            # remove whisperLabel/setWhisperChunk, adiciona BubbleStack
  Game.ts                           # spawn secretario+bibliotecario nos cantos. NPC click → ChatWindowManager
  Player.ts                         # bloqueia W/A/S/D quando input do chat tem foco

src/ui/
  AgentToast.ts                     # listener SSE agent_message → roteia pra BubbleStack + ChatWindowManager
  
src/main.ts                         # wire PlayerChatInput, T key listener global, ChatWindowManager singleton
index.html                          # remove <div id="chat-panel">, link chat-windows.css
```

### Deletados

```
src/ui/ChatPanel.ts                 # substituído por ChatWindow + Manager
```

## 14. Testing strategy

| Camada | Estratégia |
|---|---|
| `db.py` + `agent_messages.py` | pytest com `:memory:` SQLite, valida insert/history/recent |
| `handoff.py` | pytest mockando `llm.call`, valida JSON parsing + cache hit |
| Endpoints novos | pytest com FastAPI TestClient, mock do Crew kickoff |
| `agent_messages_tools` | pytest valida que tools retornam shape esperado |
| `SpeechBubble` (Pixi) | unit test em jsdom + Pixi headless? (provavelmente smoke test manual) |
| `BubbleStack` lógica | pure JS test: pushSay + verifica reposition + TTL |
| `ChatWindowManager` | jsdom: open 3 windows simultâneos, verifica DOM + z-index |
| `PlayerChatInput` | jsdom: T abre/fecha, Enter envia + bloqueia W/A/S/D |
| Pipeline integração | smoke test: roda 1 card real, verifica que `agent_messages` table tem `say` rows |

## 15. Riscos e mitigações

| Risco | Mitigação |
|---|---|
| LLM do handoff lento e bloqueia step | `lru_cache` reduz repetição. Timeout de 5s no `llm.call`, fallback templado. |
| SSE perde mensagens (cliente desconecta/reconecta) | `loadHistory()` ao abrir janela carrega tudo do SQLite — não depende só do stream. |
| Playwright/janelas/Pixi z-fighting | `BubbleStack.container` é child do NPC, herda Y-sort. ChatWindow é HTML over canvas (z-index 1100+). Sem conflito. |
| Player abre 20 janelas e trava | Limite soft no `ChatWindowManager`: warn em 10, força fechar mais antiga em 15. |
| Whisper buffer cresce demais entre flushes | Debounce de 500ms + truncate a 5 linhas (~150 chars). DB grava no máx 1x/s. |
| Secretário sem contexto fresh (cache de tools) | Tools sempre leem `_tasks` do planner_loop in-memory + DB live. Sem cache de contexto. |
| Multi-pipeline simultâneo confunde Secretário | `get_pipeline_status` retorna lista de cards ativos (não 1 só). LLM lida. |

## 16. Sucesso

- Bolha de fala bate visualmente com a referência Habbo moderno
- Whisper aparece quando agente trabalha e some quando termina (sem ficar "preso")
- Handoff entre agentes mostra mensagem natural ("Pesquisa pronta, 5 refs, passando pro Copy")
- Player aperta T → input abre, digita pergunta, Secretário responde dentro de 5s
- Player abre 3 chats simultâneos (ex: Researcher, Designer, Bibliotecário) e cada um tem histórico próprio
- Bug de "mesma auto-mensagem em todos agentes" desaparece
- SQLite `agent_messages` cresce ~500 rows por projeto rodado
