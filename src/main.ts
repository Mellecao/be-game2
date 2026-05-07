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
import { ChatWindowManager } from "./ui/ChatWindowManager";
import { PlayerChatInput } from "./ui/PlayerChatInput";
import type { NPC } from "./game/NPC";

async function bootstrap() {
  const identity = await NicknameModal.getOrPrompt();
  const toast = new AgentToast();
  const tasksPanel = new TasksPanel();
  new AgentsPanel();

  // llm_chunk callback é mantido por compatibilidade, mas o whisper persistido
  // agora chega via SSE 'agent_message' e é roteado direto pelo AgentToast.
  connectEventStream(toast, tasksPanel);

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

    // Build NPC registry (id → NPC) and wire ChatWindowManager + AgentToast routing.
    // Whisper agora vem via SSE agent_message (roteado pelo AgentToast).
    const npcRegistry: Record<string, NPC> = {};
    for (const npc of game.npcs) npcRegistry[npc.id] = npc;

    const chatWindowManager = new ChatWindowManager();
    toast.setChatWindowManager(chatWindowManager);
    toast.setNpcRegistry(npcRegistry);

    // Player chat input (T key toggle) → POST /api/chat/secretario
    const playerInput = new PlayerChatInput({
      onSubmit: async (text: string) => {
        // 1. Bubble player imediato (Phase 11 vai adicionar Player.pushSay)
        if (game.player && typeof (game.player as any).pushSay === "function") {
          (game.player as any).pushSay(text);
        }

        // 2. Whisper "..." no Secretário enquanto aguarda resposta
        const secretarioNpc = npcRegistry["secretario"];
        secretarioNpc?.setWhisper("...");

        // 3. POST endpoint — SSE 'agent_message' tipo 'reply' do Secretário
        // vai trigger pushSay automaticamente via AgentToast.routeAgentMessage
        try {
          await fetch("/api/chat/secretario", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: text }),
          });
        } catch (err) {
          console.error("chat secretario failed", err);
          secretarioNpc?.setWhisper("(erro de conexão)");
          setTimeout(() => secretarioNpc?.clearWhisper(), 3000);
        }
      },
    });

    // Listener global: T toggle (ignora se outro input já tem foco)
    window.addEventListener("keydown", (e) => {
      if (e.key !== "t" && e.key !== "T") return;
      const active = document.activeElement;
      if (active?.tagName === "INPUT" || active?.tagName === "TEXTAREA") {
        if (!playerInput.hasFocus()) return;
      }
      e.preventDefault();
      playerInput.toggle();
    });

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
