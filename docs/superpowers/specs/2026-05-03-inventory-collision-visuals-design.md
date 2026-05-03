# Design: Inventário, Colisão e Mudanças Visuais

**Data:** 2026-05-03  
**Status:** Aprovado

---

## Escopo

Seis mudanças independentes que se integram na mesma sessão de jogo:

1. Sistema de inventário com painel flutuante
2. Colisão de móveis bloqueando o jogador
3. Piso procedural com extrusão e grid
4. Remoção da porta + tile de corredor
5. Altura da parede +15%
6. Tamanho dos personagens +25%

---

## 1. Inventário

### Componentes

**`src/ui/InventoryPanel.ts`** — novo arquivo.

- Painel flutuante posicionado à direita da tela
- Visível apenas quando Building Mode está ativo (toggled pelo `BuildingPanel`)
- Exibe os 5 itens disponíveis: `sofa`, `chair`, `desk`, `table`, `window`
- Cada item mostra: ícone (preview via Canvas ou imagem estática), nome, contador `usado/4`
- Ao clicar num item com `usado < 4`: instancia `NitroFurniture` no centro do quarto e registra no editor
- Ao clicar com `usado >= 4`: botão desabilitado

**Contagem de itens em uso:** `InventoryPanel` recebe referência ao array `game.furniture` e filtra por `item.id.startsWith(itemId)` para contar instâncias ativas (não removidas).

**IDs de múltiplas instâncias:** `sofa`, `sofa_2`, `sofa_3`, `sofa_4` — sufixo numérico incremental.

### API (backend)

Três endpoints novos em `server/api.py`:

| Método | Path | Descrição |
|--------|------|-----------|
| GET | `/api/inventory` | Lista `{item_id, quantity}` global |
| POST | `/api/inventory/add` | Incrementa quantity (max 4) |
| POST | `/api/inventory/remove` | Decrementa quantity |

Modelos Pydantic:
```python
class InventoryAction(BaseModel):
    item_id: str
    owner_id: str | None = None
```

### Banco de Dados

```sql
create table public.inventory_items (
    id          bigserial primary key,
    item_id     text not null,
    quantity    integer not null default 1,
    owner_id    text,                 -- null = global
    created_at  timestamptz not null default now(),
    unique (item_id, owner_id)
);
alter table public.inventory_items disable row level security;
```

Seed inicial (1 de cada item) executado na primeira chamada de GET se tabela estiver vazia.

---

## 2. Colisão

### Componente

**`src/game/CollisionMap.ts`** — novo arquivo.

```typescript
export class CollisionMap {
  private grid: boolean[][];  // [row][col]
  
  constructor()
  block(col: number, row: number): void
  unblock(col: number, row: number): void
  isBlocked(col: number, row: number): boolean
  clear(): void
}
```

### Integração

**`FurnitureEditor.ts`** — recebe `CollisionMap` no construtor. Em `moveTo()` e na remoção, atualiza o mapa.

**`Player.ts`** — recebe `CollisionMap`. Em `update()`, antes de aplicar movimento:
```typescript
const nextCol = Math.round(this.worldCol + dCol);
const nextRow = Math.round(this.worldRow + dRow);
if (!collisionMap.isBlocked(nextCol, nextRow)) {
  this.worldCol += dCol;
  this.worldRow += dRow;
}
```

**`Game.ts`** — instancia `CollisionMap`, passa para `FurnitureEditor` e `Player`. Ao carregar posições salvas, popula o mapa.

### Dimensão de colisão

Cada móvel ocupa 1 tile (o tile onde `worldCol/worldRow` está arredondado). Extensível para multi-tile no futuro via `footprint: {col, row}[]` no config.

---

## 3. Piso Procedural com Extrusão

### Mudanças em `Room.ts`

Substituir `drawFloor()` (que usa nitro) por tiles procedurais isométricos:

- **Face superior:** cor `0xb0a898` (concreto claro), forma de losango isométrico
- **Face lateral esquerda:** cor `0x8a8078`, altura 4px (extrusão)
- **Face lateral direita:** cor `0x787068`, altura 4px (extrusão, mais escura)
- **Grid:** linhas sobre os tiles, cor `0x787068`, alpha 0.35

A extrusão dá sensação de volume ao piso, diferenciando visualmente da parede.

---

## 4. Porta → Tile de Corredor

### Mudanças em `Room.ts`

Remover `drawDoor()` completamente.

Adicionar `drawCorridor()`:
- 1 tile isométrico em posição `col=-1, row=4` (fora do quarto, na parede esquerda)
- Cor `0x1a1a22` (escuro, igual ao background do app)
- Sem bordas de grid
- Efeito visual: "buraco" na parede sugerindo corredor/entrada

A parede esquerda terá uma "lacuna" nessa posição para o corredor aparecer.

---

## 5. Altura da Parede

**`src/game/iso.ts`**

```typescript
// Antes:
export const WALL_HEIGHT = 110;
// Depois:
export const WALL_HEIGHT = 127; // +15%
```

---

## 6. Tamanho dos Personagens

**`src/game/Player.ts`**

```typescript
// Scale 1.6 → 2.0
p.sprite.scale.set(2.0);
// updateSprite():
this.sprite.scale.x = 2.0 * flip;
```

**`src/game/NPC.ts`** — mesma escala ajustada de 1.6 → 2.0.

Shadow: escala atual `(0.9, 0.6)` → `(1.1, 0.75)` proporcional.

---

## Arquivos Modificados

| Arquivo | Mudança |
|---------|---------|
| `src/ui/InventoryPanel.ts` | **NOVO** |
| `src/game/CollisionMap.ts` | **NOVO** |
| `src/game/Game.ts` | Integra CollisionMap, InventoryPanel, novos furniture configs |
| `src/game/FurnitureEditor.ts` | Notifica CollisionMap em move/remove |
| `src/game/Player.ts` | Consulta CollisionMap, scale 2.0 |
| `src/game/NPC.ts` | Scale 2.0 |
| `src/game/Room.ts` | Piso procedural, corredor, remove porta |
| `src/game/iso.ts` | WALL_HEIGHT 127 |
| `src/game/constants.ts` | Adiciona `nitroTable` ao FURNITURE_CONFIG |
| `server/api.py` | Endpoints de inventário |
| `supabase/schema.sql` | Tabela `inventory_items` |

---

## Fora do Escopo

- Pathfinding / desvio automático de móveis
- Inventário por jogador (estrutura preparada via `owner_id nullable`)
- Móveis multi-tile
- Animação de colocação de item
