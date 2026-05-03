import { Application } from "pixi.js";
import { Game } from "./game/Game";
import { ChatPanel } from "./ui/ChatPanel";
import { BuildingPanel } from "./ui/BuildingPanel";
import { ASSETS } from "./game/constants";

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

  const chat = new ChatPanel();

  game.setNpcClickHandler((npc) => {
    chat.open({
      id: npc.id,
      name: npc.displayName,
      portraitUrl: ASSETS.portraitNpc,
    });
  });

  new BuildingPanel(
    (active) => game.setBuilding(active),
    () => game.saveLayout(),
    (on) => game.setRemoveWalls(on)
  );
}

bootstrap().catch((err) => {
  console.error("Erro ao inicializar:", err);
  document.body.innerHTML = `<pre style="color:white;padding:20px">${err}</pre>`;
});
