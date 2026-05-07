import { Application } from "pixi.js";
import { Game } from "./game/Game";
import { ChatPanel } from "./ui/ChatPanel";
import { BuildingPanel } from "./ui/BuildingPanel";
import { InventoryPanel } from "./ui/InventoryPanel";
import { AgentPanel } from "./ui/AgentPanel";
import { AgentConfigModal } from "./ui/AgentConfigModal";
import { ASSETS } from "./game/constants";
import { NicknameModal } from "./ui/NicknameModal";
import { MultiplayerService } from "./multiplayer/MultiplayerService";
import { AgentToast, connectEventStream } from "./ui/AgentToast";
import { TasksPanel } from "./ui/TasksPanel";
import { AgentsPanel } from "./ui/AgentsPanel";

async function bootstrap() {
  const identity = await NicknameModal.getOrPrompt();
  const toast = new AgentToast();
  const tasksPanel = new TasksPanel();
  new AgentsPanel();

  // Whisper chunks are routed to NPCs after game.init (wired below)
  let npcWhisperCallback: ((taskId: string, chunk: string) => void) | undefined;
  connectEventStream(toast, tasksPanel, (taskId, chunk) => {
    npcWhisperCallback?.(taskId, chunk);
  });

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

  try {
    const game = new Game(app);
    await game.init(container, mp);
    game.player.setName(identity.name);
    window.addEventListener('beforeunload', () => mp.disconnect());

    const chat = new ChatPanel();

    // Wire task status → NPC indicator color (yellow idle, green working)
    tasksPanel.setAgentWorkingCallback((activeIds) => {
      for (const npc of game.npcs) {
        npc.setWorking(activeIds.has(npc.id));
      }
    });

    // Wire LLM streaming chunks → whisper bubble on the active NPC
    npcWhisperCallback = (_taskId: string, chunk: string) => {
      for (const npc of game.npcs) {
        if (npc.isWorking) {
          npc.setWhisperChunk(chunk);
          break;
        }
      }
    };

    game.setNpcClickHandler((npc) => {
      chat.open({
        id: npc.id,
        name: npc.displayName,
        portraitUrl: ASSETS.portraitNpc,
      });
    });

    const inventory = new InventoryPanel(
      () => game.getFurnitureList(),
      (itemId) => game.spawnFurniture(itemId),
      (itemId) => game.removeFurniture(itemId)
    );

    new BuildingPanel(
      (active) => {
        game.setBuilding(active);
        active ? inventory.show() : inventory.hide();
      },
      () => game.saveLayout(),
      (on) => game.setRemoveWalls(on)
    );

    const agentModal = new AgentConfigModal();

    new AgentPanel((active) => {
      game.setAgentMode(active);
    });

    game.agentEditor.onSelect = (npc) => agentModal.open(npc);
  } catch (err) {
    mp.disconnect();
    throw err;
  }
}

bootstrap().catch((err) => {
  console.error("Erro ao inicializar:", err);
  document.body.innerHTML = `<pre style="color:white;padding:20px">${err}</pre>`;
});
