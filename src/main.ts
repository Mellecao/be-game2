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

  const chat = new ChatPanel();

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
}

bootstrap().catch((err) => {
  console.error("Erro ao inicializar:", err);
  document.body.innerHTML = `<pre style="color:white;padding:20px">${err}</pre>`;
});
