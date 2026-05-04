# Real-Time Multiplayer — Design Spec

**Data:** 2026-05-04  
**Status:** Aprovado

---

## Contexto

O jogo (PixiJS v8 + FastAPI + Supabase) tem um único jogador local se movendo numa sala isométrica. O objetivo é adicionar suporte a N jogadores simultâneos: ao entrar na sala, cada jogador vê os outros em tempo real — posição, direção e apelido.

---

## Decisões de design

| Questão | Decisão |
|---|---|
| Identidade | Anônima com apelido digitado em modal |
| Avatar | `spriteChar` aleatório (1–4) atribuído na entrada |
| Nome visível | Label flutuante acima do sprite, sempre visível |
| Jogadores simultâneos | N (ilimitado — Supabase Presence escala nativamente) |
| Mecanismo real-time | Supabase Realtime: Presence (join/leave) + Broadcast (posição) |
| Novo endpoint backend | Nenhum — tudo no frontend via Supabase Realtime |

---

## Arquitetura

### Novas peças

```
src/
  multiplayer/
    MultiplayerService.ts   ← toda lógica Supabase Realtime
    RemotePlayer.ts         ← sprite interpolado de outro jogador
  ui/
    NicknameModal.ts        ← modal HTML/CSS de entrada
```

### Arquivos modificados

```
src/
  game/Game.ts    ← gerencia Map<id, RemotePlayer>, escuta MultiplayerService
  main.ts         ← mostra NicknameModal, instancia MultiplayerService antes do Game
```

### Fluxo de inicialização

```
main.ts
  → NicknameModal.getOrPrompt()      → { id, name, spriteChar }
  → MultiplayerService.connect(...)
      Presence track { id, name, spriteChar }
      setInterval 50ms → Broadcast player-move
  → Game.init(container, mp)
      presenceState() → cria RemotePlayer para cada jogador já na sala
      onPlayerJoined  → cria RemotePlayer
      onPlayerLeft    → destrói RemotePlayer
      onPlayerMoved   → atualiza target do RemotePlayer
```

---

## MultiplayerService

Canal Supabase único: `room:main`

### Presence

- `track({ id, name, spriteChar })` ao conectar
- Evento `presence_diff.joins` → `onPlayerJoined(RemotePlayerData)`
- Evento `presence_diff.leaves` → `onPlayerLeft(id)`
- `presenceState()` retorna todos os jogadores já presentes ao entrar

### Broadcast

- Evento `player-move` com payload `{ id, col, row, dir }`
- Enviado via `setInterval(50ms)` — throttle fixo, independente do framerate
- Recebido → `onPlayerMoved(id, col, row, dir)`

### Interface pública

```ts
type RemotePlayerData = { id: string; name: string; spriteChar: number }

class MultiplayerService {
  onPlayerJoined: (data: RemotePlayerData) => void
  onPlayerLeft:   (id: string) => void
  onPlayerMoved:  (id: string, col: number, row: number, dir: string) => void

  connect(playerId: string, name: string, spriteChar: number): Promise<void>
  sendPosition(col: number, row: number, dir: string): void
  disconnect(): void
}
```

### Config

Lê `VITE_SUPABASE_URL` e `VITE_SUPABASE_ANON_KEY` do `.env`.  
Usa anon key no frontend (nunca a service role key).

---

## RemotePlayer

`Container` do PixiJS com os mesmos assets de sprite do `Player`.

### Renderização

- Sprites idle/walk por direção (front/back/side), com flip para `left` — mesmos assets do `Player` local (`/avatar/...`)
- `spriteChar` (1–4) mapeia para uma tint de cor aplicada ao sprite via `sprite.tint`:
  - 1 → `0xffffff` (branco — sem tint)
  - 2 → `0x88ccff` (azul)
  - 3 → `0x88ffaa` (verde)
  - 4 → `0xffaa88` (laranja)
- `PixiJS Text` com o apelido centralizado acima do sprite, sempre visível

### Interpolação

Mantém `targetCol/targetRow` (última posição recebida) e `worldCol/worldRow` (posição atual renderizada).

A cada frame:
```
worldCol += (targetCol - worldCol) * LERP_FACTOR * dt
worldRow += (targetRow - worldRow) * LERP_FACTOR * dt
```

`LERP_FACTOR = 0.2` — suaviza o movimento entre os updates de 50ms.

### API

```ts
class RemotePlayer extends Container {
  static async load(data: RemotePlayerData): Promise<RemotePlayer>
  setTarget(col: number, row: number, dir: string): void
  update(dt: number): void
}
```

---

## NicknameModal

Componente HTML/CSS puro (sem biblioteca), consistente com os outros painéis do jogo.

### UX

- Overlay escuro sobre o canvas antes do jogo iniciar
- Input "Como quer ser chamado?" com botão "Entrar"
- Botão desabilitado enquanto o campo está vazio
- Enter também confirma

### Fluxo

```
1. Verifica localStorage["be-game-identity"]
2. Se existir → retorna { id, name, spriteChar } sem mostrar o modal
3. Se não existir → mostra modal, aguarda confirmação
4. Ao confirmar:
   - playerId = crypto.randomUUID()
   - spriteChar = Math.ceil(Math.random() * 4)
   - Salva no localStorage
   - Retorna { id, name, spriteChar }
```

### API

```ts
class NicknameModal {
  static async getOrPrompt(): Promise<{ id: string; name: string; spriteChar: number }>
}
```

---

## Integração no Game

```ts
// Game.ts
private remotePlayers = new Map<string, RemotePlayer>()

// No init():
mp.onPlayerJoined = async (data) => {
  const rp = await RemotePlayer.load(data)
  this.world.addChild(rp)
  this.remotePlayers.set(data.id, rp)
}
mp.onPlayerLeft = (id) => {
  this.remotePlayers.get(id)?.destroy()
  this.remotePlayers.delete(id)
}
mp.onPlayerMoved = (id, col, row, dir) => {
  this.remotePlayers.get(id)?.setTarget(col, row, dir)
}

// No update():
// Player.dir precisa ser exposto como getter público: get currentDir(): string
mp.sendPosition(this.player.worldCol, this.player.worldRow, this.player.currentDir)
for (const rp of this.remotePlayers.values()) rp.update(dt)

// No sortDepth():
...this.remotePlayers.values() // incluídos no depth sort
```

---

## Variáveis de ambiente necessárias

Adicionar ao `.env`:
```
VITE_SUPABASE_URL=...
VITE_SUPABASE_ANON_KEY=...
```

(Já existem `SUPABASE_URL` e `SUPABASE_SERVICE_ROLE_KEY` para o servidor Python — as vars do frontend são diferentes e usam a anon key.)

---

## O que não muda

- Lógica de movimento do `Player` local — inalterada (exceto expor `currentDir` getter)
- Colisão — só o jogador local verifica colisão; remotos são visuais
- NPCs e furniture — inalterados
- Backend FastAPI — nenhuma alteração necessária
