# Real-Time Multiplayer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir N jogadores simultâneos na sala isométrica, cada um vendo os outros em tempo real com posição, direção e apelido.

**Architecture:** Supabase Realtime com dois mecanismos no canal `room:main`: Presence rastreia quem está conectado (join/leave + metadados), Broadcast envia posições a cada 50ms. RemotePlayer renderiza outros jogadores com interpolação LERP para movimento fluido. NicknameModal captura apelido antes de entrar, persistindo em localStorage.

**Tech Stack:** PixiJS v8, TypeScript, Supabase Realtime JS v2 (`@supabase/supabase-js` já instalado), Vite.

---

## File Map

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `src/game/Player.ts` | Modificar | Expor getter `currentDir` público |
| `src/ui/NicknameModal.ts` | Criar | Modal HTML/CSS de entrada com apelido |
| `src/multiplayer/MultiplayerService.ts` | Criar | Toda lógica Supabase Realtime |
| `src/multiplayer/RemotePlayer.ts` | Criar | Sprite interpolado de outro jogador |
| `src/game/Game.ts` | Modificar | Gerenciar `Map<id, RemotePlayer>` |
| `src/main.ts` | Modificar | Orquestrar modal → multiplayer → game |

> **Nota:** `.env.local` já tem `VITE_SUPABASE_URL` e `VITE_SUPABASE_ANON_KEY` — nenhuma configuração adicional necessária.

---

## Task 1: Expor `Player.currentDir`

**Files:**
- Modify: `src/game/Player.ts`

- [ ] **Abrir `src/game/Player.ts` e localizar a linha `private dir: Dir = "front";` (linha 21)**

- [ ] **Adicionar getter público logo após essa linha:**

```typescript
// src/game/Player.ts — adicionar após "private dir: Dir = "front";"
get currentDir(): string {
  return this.dir;
}
```

O arquivo deve ficar assim na área das propriedades:

```typescript
private dir: Dir = "front";

get currentDir(): string {
  return this.dir;
}

// Each direction key has its own independent frame counter
```

- [ ] **Verificar que TypeScript compila sem erros:**

```
npx tsc --noEmit
```

Esperado: sem output (zero erros).

- [ ] **Commit:**

```bash
git add src/game/Player.ts
git commit -m "feat: expose currentDir getter on Player"
```

---

## Task 2: Criar `NicknameModal`

**Files:**
- Create: `src/ui/NicknameModal.ts`

- [ ] **Criar o arquivo `src/ui/NicknameModal.ts` com o conteúdo abaixo:**

```typescript
const STORAGE_KEY = 'be-game-identity'

interface Identity {
  id: string
  name: string
  spriteChar: number
}

export class NicknameModal {
  static async getOrPrompt(): Promise<Identity> {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored) {
      try {
        return JSON.parse(stored) as Identity
      } catch {
        localStorage.removeItem(STORAGE_KEY)
      }
    }
    return NicknameModal.prompt()
  }

  private static prompt(): Promise<Identity> {
    return new Promise((resolve) => {
      const overlay = document.createElement('div')
      overlay.style.cssText = `
        position: fixed; inset: 0; background: rgba(0,0,0,0.85);
        display: flex; align-items: center; justify-content: center;
        z-index: 9999; font-family: monospace;
      `

      const box = document.createElement('div')
      box.style.cssText = `
        background: #1a1a2e; border: 1px solid #444; border-radius: 8px;
        padding: 32px 40px; display: flex; flex-direction: column; gap: 16px;
        min-width: 280px; color: #fff;
      `

      const title = document.createElement('h2')
      title.textContent = 'Entrar na sala'
      title.style.cssText = 'margin: 0; font-size: 18px; font-weight: 600;'

      const input = document.createElement('input')
      input.type = 'text'
      input.placeholder = 'Como quer ser chamado?'
      input.maxLength = 20
      input.style.cssText = `
        background: #111; border: 1px solid #555; border-radius: 4px;
        color: #fff; font-family: monospace; font-size: 14px;
        padding: 8px 12px; outline: none;
      `

      const btn = document.createElement('button')
      btn.textContent = 'Entrar'
      btn.disabled = true
      btn.style.cssText = `
        background: #3b5bdb; border: none; border-radius: 4px;
        color: #fff; font-family: monospace; font-size: 14px;
        padding: 10px; cursor: pointer; opacity: 0.5; transition: opacity 0.2s;
      `

      input.addEventListener('input', () => {
        const ok = input.value.trim().length > 0
        btn.disabled = !ok
        btn.style.opacity = ok ? '1' : '0.5'
      })

      const confirm = () => {
        const name = input.value.trim()
        if (!name) return
        const identity: Identity = {
          id: crypto.randomUUID(),
          name,
          spriteChar: Math.ceil(Math.random() * 4),
        }
        localStorage.setItem(STORAGE_KEY, JSON.stringify(identity))
        overlay.remove()
        resolve(identity)
      }

      btn.addEventListener('click', confirm)
      input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') confirm()
      })

      box.append(title, input, btn)
      overlay.appendChild(box)
      document.body.appendChild(overlay)
      input.focus()
    })
  }
}
```

- [ ] **Verificar TypeScript:**

```
npx tsc --noEmit
```

Esperado: zero erros.

- [ ] **Teste manual rápido — abrir o `main.ts` temporariamente e adicionar no topo do `bootstrap()`:**

```typescript
import { NicknameModal } from './ui/NicknameModal'
const id = await NicknameModal.getOrPrompt()
console.log('[modal test]', id)
```

Iniciar o dev server (`npm run dev`), abrir `http://localhost:5173`, verificar:
- Overlay escuro aparece com input e botão desabilitado
- Digitar um nome habilita o botão
- Pressionar Enter ou clicar confirma → console.log mostra `{ id: "uuid...", name: "...", spriteChar: 1-4 }`
- Recarregar a página → modal **não** aparece de novo (vem do localStorage)
- Para resetar: `localStorage.removeItem('be-game-identity')` no console do browser

Remover o código de teste após verificar.

- [ ] **Commit:**

```bash
git add src/ui/NicknameModal.ts
git commit -m "feat: NicknameModal com persistencia em localStorage"
```

---

## Task 3: Criar `MultiplayerService`

**Files:**
- Create: `src/multiplayer/MultiplayerService.ts`

- [ ] **Criar a pasta `src/multiplayer/` e o arquivo `src/multiplayer/MultiplayerService.ts`:**

```typescript
import { createClient, SupabaseClient, RealtimeChannel } from '@supabase/supabase-js'

export type RemotePlayerData = { id: string; name: string; spriteChar: number }

export class MultiplayerService {
  onPlayerJoined: ((data: RemotePlayerData) => void) | null = null
  onPlayerLeft: ((id: string) => void) | null = null
  onPlayerMoved: ((id: string, col: number, row: number, dir: string) => void) | null = null

  private supabase: SupabaseClient
  private channel: RealtimeChannel | null = null
  private myId = ''
  private pendingPos: { col: number; row: number; dir: string } | null = null
  private intervalId: ReturnType<typeof setInterval> | null = null

  constructor() {
    this.supabase = createClient(
      import.meta.env.VITE_SUPABASE_URL as string,
      import.meta.env.VITE_SUPABASE_ANON_KEY as string
    )
  }

  async connect(playerId: string, name: string, spriteChar: number): Promise<void> {
    this.myId = playerId

    this.channel = this.supabase.channel('room:main', {
      config: { presence: { key: playerId } },
    })

    this.channel
      .on('presence', { event: 'join' }, ({ key, newPresences }) => {
        if (key === this.myId) return
        const p = (newPresences as any[])[0]
        this.onPlayerJoined?.({ id: key, name: p.name, spriteChar: p.spriteChar })
      })
      .on('presence', { event: 'leave' }, ({ key }) => {
        if (key === this.myId) return
        this.onPlayerLeft?.(key)
      })
      .on('broadcast', { event: 'player-move' }, ({ payload }) => {
        if (payload.id === this.myId) return
        this.onPlayerMoved?.(payload.id, payload.col, payload.row, payload.dir)
      })

    await new Promise<void>((resolve) => {
      this.channel!.subscribe(async (status) => {
        if (status !== 'SUBSCRIBED') return
        await this.channel!.track({ name, spriteChar })

        // Announce players already present in the room
        const state = this.channel!.presenceState<{ name: string; spriteChar: number }>()
        for (const [key, presences] of Object.entries(state)) {
          if (key === playerId) continue
          const p = presences[0]
          this.onPlayerJoined?.({ id: key, name: p.name, spriteChar: p.spriteChar })
        }
        resolve()
      })
    })

    this.intervalId = setInterval(() => {
      if (!this.pendingPos || !this.channel) return
      this.channel.send({
        type: 'broadcast',
        event: 'player-move',
        payload: { id: this.myId, ...this.pendingPos },
      })
      this.pendingPos = null
    }, 50)
  }

  sendPosition(col: number, row: number, dir: string): void {
    this.pendingPos = { col, row, dir }
  }

  disconnect(): void {
    if (this.intervalId !== null) clearInterval(this.intervalId)
    if (this.channel) this.supabase.removeChannel(this.channel)
    this.channel = null
  }
}
```

- [ ] **Verificar TypeScript:**

```
npx tsc --noEmit
```

Esperado: zero erros.

- [ ] **Commit:**

```bash
git add src/multiplayer/MultiplayerService.ts
git commit -m "feat: MultiplayerService com Supabase Presence e Broadcast"
```

---

## Task 4: Criar `RemotePlayer`

**Files:**
- Create: `src/multiplayer/RemotePlayer.ts`

- [ ] **Criar `src/multiplayer/RemotePlayer.ts`:**

```typescript
import { Container, Sprite, Texture, Assets, Text, TextStyle } from 'pixi.js'
import { isoToScreen } from '../game/iso'
import { RemotePlayerData } from './MultiplayerService'

type DirKey = 'front' | 'back' | 'side'

const LERP_FACTOR = 0.2
const WALK_FPS = 8
const IDLE_FPS = 4
const DIRS: DirKey[] = ['front', 'back', 'side']

const TINTS: Record<number, number> = {
  1: 0xffffff,
  2: 0x88ccff,
  3: 0x88ffaa,
  4: 0xffaa88,
}

export class RemotePlayer extends Container {
  private sprite!: Sprite
  private idleTextures: Record<DirKey, Texture[]> = { front: [], back: [], side: [] }
  private walkTextures: Record<DirKey, Texture[]> = { front: [], back: [], side: [] }

  private dirKey: DirKey = 'front'
  private flip = 1
  private moving = false

  private idleFrame: Record<DirKey, number> = { front: 0, back: 0, side: 0 }
  private idleTimer: Record<DirKey, number> = { front: 0, back: 0, side: 0 }
  private walkFrame: Record<DirKey, number> = { front: 0, back: 0, side: 0 }
  private walkTimer: Record<DirKey, number> = { front: 0, back: 0, side: 0 }

  worldCol = 0.5
  worldRow = 4.5
  private targetCol = 0.5
  private targetRow = 4.5

  static async load(data: RemotePlayerData): Promise<RemotePlayer> {
    const rp = new RemotePlayer()

    // Assets.load é cacheado pelo PixiJS — sem custo se Player já carregou os mesmos arquivos
    const [shadowTex, ...rest] = await Promise.all([
      Assets.load('/avatar/shadow.png'),
      ...[1, 2, 3, 4, 5].map((i) => Assets.load(`/avatar/front_${i}_iddle.png`)),
      ...[1, 2, 3, 4, 5].map((i) => Assets.load(`/avatar/back_${i}_iddle.png`)),
      ...[1, 2, 3, 4, 5].map((i) => Assets.load(`/avatar/side_${i}_iddle.png`)),
      ...[1, 2, 3, 4, 5].map((i) => Assets.load(`/avatar/front_${i}_walking.png`)),
      ...[1, 2, 3, 4, 5].map((i) => Assets.load(`/avatar/back_${i}_walking.png`)),
      ...[1, 2, 3, 4, 5].map((i) => Assets.load(`/avatar/side_${i}_walking.png`)),
    ])

    rp.idleTextures.front = rest.slice(0, 5)
    rp.idleTextures.back  = rest.slice(5, 10)
    rp.idleTextures.side  = rest.slice(10, 15)
    rp.walkTextures.front = rest.slice(15, 20)
    rp.walkTextures.back  = rest.slice(20, 25)
    rp.walkTextures.side  = rest.slice(25, 30)

    const shadow = new Sprite(shadowTex)
    shadow.anchor.set(0.5, 0.5)
    shadow.alpha = 0.45
    shadow.y = 4
    shadow.scale.set(1.1, 0.75)
    rp.addChild(shadow)

    rp.sprite = new Sprite(rp.idleTextures.front[0])
    rp.sprite.anchor.set(0.5, 1)
    rp.sprite.scale.set(2.64)
    rp.sprite.tint = TINTS[data.spriteChar] ?? 0xffffff
    rp.addChild(rp.sprite)

    const label = new Text({
      text: data.name,
      style: new TextStyle({
        fontSize: 12,
        fill: 0xffffff,
        fontFamily: 'monospace',
        stroke: { color: 0x000000, width: 3 },
      }),
    })
    label.anchor.set(0.5, 1)
    label.y = -(rp.sprite.height + 6)
    rp.addChild(label)

    rp.syncScreen()
    return rp
  }

  setTarget(col: number, row: number, dir: string): void {
    this.targetCol = col
    this.targetRow = row
    switch (dir) {
      case 'front': this.dirKey = 'front'; this.flip =  1; break
      case 'back':  this.dirKey = 'back';  this.flip =  1; break
      case 'right': this.dirKey = 'side';  this.flip =  1; break
      case 'left':  this.dirKey = 'side';  this.flip = -1; break
    }
  }

  update(dt: number): void {
    const dCol = this.targetCol - this.worldCol
    const dRow = this.targetRow - this.worldRow
    this.moving = Math.hypot(dCol, dRow) > 0.05

    this.worldCol += dCol * LERP_FACTOR
    this.worldRow += dRow * LERP_FACTOR

    const idleTicks = 60 / IDLE_FPS
    const walkTicks = 60 / WALK_FPS
    for (const k of DIRS) {
      this.idleTimer[k] += dt
      if (this.idleTimer[k] >= idleTicks) {
        this.idleTimer[k] -= idleTicks
        this.idleFrame[k] = (this.idleFrame[k] + 1) % 5
      }
      this.walkTimer[k] += dt
      if (this.walkTimer[k] >= walkTicks) {
        this.walkTimer[k] -= walkTicks
        this.walkFrame[k] = (this.walkFrame[k] + 1) % 5
      }
    }

    this.sprite.texture = this.moving
      ? this.walkTextures[this.dirKey][this.walkFrame[this.dirKey]]
      : this.idleTextures[this.dirKey][this.idleFrame[this.dirKey]]
    this.sprite.scale.x = 2.64 * this.flip

    this.syncScreen()
  }

  private syncScreen(): void {
    const pos = isoToScreen(this.worldCol, this.worldRow)
    this.x = pos.x
    this.y = pos.y
  }
}
```

- [ ] **Verificar TypeScript:**

```
npx tsc --noEmit
```

Esperado: zero erros.

- [ ] **Commit:**

```bash
git add src/multiplayer/RemotePlayer.ts
git commit -m "feat: RemotePlayer com interpolacao LERP e label de nome"
```

---

## Task 5: Atualizar `Game.ts`

**Files:**
- Modify: `src/game/Game.ts`

- [ ] **Adicionar imports no topo de `src/game/Game.ts`:**

```typescript
// Adicionar junto aos imports existentes
import { MultiplayerService } from '../multiplayer/MultiplayerService'
import { RemotePlayer } from '../multiplayer/RemotePlayer'
```

- [ ] **Adicionar propriedade `remotePlayers` e `mp` na classe `Game` (junto às outras propriedades):**

```typescript
// Adicionar após "private onNpcClick: NPCClickHandler | null = null;"
private remotePlayers = new Map<string, RemotePlayer>()
private mp: MultiplayerService | null = null
```

- [ ] **Alterar a assinatura de `init` para aceitar o `MultiplayerService`:**

```typescript
// Antes:
async init(container: HTMLElement) {

// Depois:
async init(container: HTMLElement, mp?: MultiplayerService) {
```

- [ ] **Adicionar o bloco de wiring do multiplayer ao final de `init()`, antes de `this.handleResize()`:**

```typescript
// Adicionar antes de: this.handleResize()
if (mp) {
  this.mp = mp

  mp.onPlayerJoined = async (data) => {
    const rp = await RemotePlayer.load(data)
    this.world.addChild(rp)
    this.remotePlayers.set(data.id, rp)
  }

  mp.onPlayerLeft = (id) => {
    const rp = this.remotePlayers.get(id)
    if (rp) {
      this.world.removeChild(rp)
      rp.destroy()
      this.remotePlayers.delete(id)
    }
  }

  mp.onPlayerMoved = (id, col, row, dir) => {
    this.remotePlayers.get(id)?.setTarget(col, row, dir)
  }
}
```

- [ ] **Atualizar o método `update()` para iterar remotePlayers e enviar posição:**

```typescript
// Antes:
private update(dt: number) {
  this.player.update(dt);
  for (const npc of this.npcs) npc.update(dt);
  this.sortDepth();
}

// Depois:
private update(dt: number) {
  this.player.update(dt);
  for (const npc of this.npcs) npc.update(dt);
  for (const rp of this.remotePlayers.values()) rp.update(dt);
  this.mp?.sendPosition(this.player.worldCol, this.player.worldRow, this.player.currentDir);
  this.sortDepth();
}
```

- [ ] **Atualizar `sortDepth()` para incluir remotePlayers no depth sort:**

```typescript
// Antes:
const items: { obj: Container; y: number }[] = [
  { obj: this.player, y: this.player.y },
  ...this.npcs.map((n) => ({ obj: n as Container, y: n.y })),
  ...this.furniture.map((f) => ({ obj: f as Container, y: f.y })),
];

// Depois:
const items: { obj: Container; y: number }[] = [
  { obj: this.player, y: this.player.y },
  ...[...this.remotePlayers.values()].map((rp) => ({ obj: rp as Container, y: rp.y })),
  ...this.npcs.map((n) => ({ obj: n as Container, y: n.y })),
  ...this.furniture.map((f) => ({ obj: f as Container, y: f.y })),
];
```

- [ ] **Verificar TypeScript:**

```
npx tsc --noEmit
```

Esperado: zero erros.

- [ ] **Commit:**

```bash
git add src/game/Game.ts
git commit -m "feat: Game integra MultiplayerService e gerencia RemotePlayers"
```

---

## Task 6: Atualizar `main.ts`

**Files:**
- Modify: `src/main.ts`

- [ ] **Adicionar imports no topo de `src/main.ts`:**

```typescript
// Adicionar junto aos imports existentes
import { NicknameModal } from './ui/NicknameModal'
import { MultiplayerService } from './multiplayer/MultiplayerService'
```

- [ ] **Substituir o início da função `bootstrap()` para incluir modal e multiplayer antes do `game.init()`:**

```typescript
// Antes:
async function bootstrap() {
  const app = new Application();
  await app.init({
    width: window.innerWidth,
    height: window.innerHeight,
    background: 0x1a1a22,
    antialias: false,
    roundPixels: true,
  });

  const container = document.getElementById("game-container");
  if (!container) throw new Error("game-container nao encontrado");

  const game = new Game(app);
  await game.init(container);

// Depois:
async function bootstrap() {
  const identity = await NicknameModal.getOrPrompt();

  const app = new Application();
  await app.init({
    width: window.innerWidth,
    height: window.innerHeight,
    background: 0x1a1a22,
    antialias: false,
    roundPixels: true,
  });

  const container = document.getElementById("game-container");
  if (!container) throw new Error("game-container nao encontrado");

  const mp = new MultiplayerService();
  await mp.connect(identity.id, identity.name, identity.spriteChar);

  const game = new Game(app);
  await game.init(container, mp);
```

O restante de `bootstrap()` (ChatPanel, BuildingPanel, etc.) permanece **inalterado**.

- [ ] **Verificar TypeScript:**

```
npx tsc --noEmit
```

Esperado: zero erros.

- [ ] **Commit:**

```bash
git add src/main.ts
git commit -m "feat: main orquestra NicknameModal e MultiplayerService antes do game"
```

---

## Task 7: Teste de integração com dois jogadores

**Pré-requisito:** servidor Python rodando (`uvicorn server.api:app --reload`) e Vite rodando (`npm run dev`).

- [ ] **Abrir a primeira aba em `http://localhost:5173`**
  - Modal aparece → digitar "Jogador A" → clicar Entrar
  - Verificar que o jogo carrega normalmente com o personagem local

- [ ] **Abrir uma segunda aba (ou outro browser) em `http://localhost:5173`**
  - Limpar localStorage antes se necessário: `localStorage.removeItem('be-game-identity')` no console
  - Modal aparece → digitar "Jogador B" → clicar Entrar
  - Verificar que na **segunda aba** aparece o sprite do Jogador A na posição inicial, com o label "Jogador A" acima

- [ ] **Verificar na primeira aba** que o sprite do Jogador B também apareceu

- [ ] **Mover o Jogador A (WASD)** — verificar que o movimento aparece em tempo real na segunda aba com animação fluida (não saltada)

- [ ] **Mover o Jogador B** — verificar que aparece na primeira aba

- [ ] **Fechar a aba do Jogador B** — verificar que o sprite do Jogador B desaparece da primeira aba em alguns segundos (timeout de presence do Supabase é ~10s)

- [ ] **Abrir uma terceira aba com "Jogador C"** — verificar que tanto A quanto C vêem uns aos outros e ao Jogador A já presente

- [ ] **Commit final:**

```bash
git add -A
git commit -m "feat: multiplayer real-time funcional com N jogadores"
```
