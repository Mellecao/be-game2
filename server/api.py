import asyncio
import base64
import datetime
import json
import os
import queue as _queue_mod
import re
from contextlib import asynccontextmanager
from pathlib import Path as _Path

import yaml as _yaml
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from crewai import Crew
from dotenv import load_dotenv

from .agents import create_copywriter, create_developer, create_planner, create_vendedor
from .tasks import create_chat_task, create_dev_task, create_planner_task
from .supabase_client import get_supabase
from . import event_bus, planner_loop

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = get_supabase()
    _ensure_agents_seed(db)
    _sync_agent_configs(db)
    planner_loop.start()
    yield


app = FastAPI(title="BE-Game Agent API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    npc_id: str = "copywriter"


class ChatResponse(BaseModel):
    response: str
    npc_id: str


class FurnitureItem(BaseModel):
    id: str
    col: int
    row: int
    direction: int
    removed: bool = False


class AgentUpdate(BaseModel):
    display_name: str | None = None
    role: str | None = None
    goal: str | None = None
    backstory: str | None = None
    col: float | None = None
    row: float | None = None


class VaultKnowledgeCreate(BaseModel):
    agent_id: str
    title: str
    content: str
    ace_type: str          # atlas|calendar|cards|efforts|resources|sources
    ace_subtype: str | None = None
    tags: list[str] = []
    rank: int | None = None
    effort_status: str | None = None   # on|ongoing|simmering
    date: str | None = None
    source_url: str | None = None
    source_author: str | None = None
    image_base64: str | None = None
    image_filename: str | None = None


class VaultKnowledgeDelete(BaseModel):
    path: str
    agent_id: str


AGENT_SEED = [
    {
        "id": "copywriter",
        "display_name": "Copywriter",
        "role": "Copywriter de Landing Pages",
        "goal": "Conversar com o usuario para entender briefings de landing pages e gerar textos persuasivos quando solicitado.",
        "backstory": "Voce e um copywriter senior da Black Elephant, especializado em landing pages para empresas de tecnologia. Conversa de forma direta e amigavel, em portugues brasileiro. Quando o usuario pedir uma copy, estrutura em Markdown com headline, hero, beneficios, CTA e FAQ.",
        "col": 7.0,
        "row": 3.0,
        "sprite_char": 3,
    },
    {
        "id": "vendedor",
        "display_name": "Vendedor",
        "role": "Consultor de Vendas",
        "goal": "Identificar oportunidades de negocio e ajudar a fechar contratos com clientes potenciais.",
        "backstory": "Voce e um consultor de vendas experiente da Black Elephant, focado em sites e apps para pequenas empresas.",
        "col": 3.0,
        "row": 3.0,
        "sprite_char": 2,
    },
    {
        "id": "programador",
        "display_name": "Programador",
        "role": "Desenvolvedor Full-Stack / Creative Technologist",
        "goal": "Entender o que o usuario quer construir e usar a ferramenta open_claude_cli para criar a pasta e iniciar o Claude CLI com um prompt detalhado de desenvolvimento.",
        "backstory": "Voce e um desenvolvedor criativo da Black Elephant especializado em sites institucionais imersivos com Three.js, GSAP e WebGL. Quando o usuario descreve um projeto, voce entende o pedido, gera um slug kebab-case, monta um prompt tecnico completo em ingles e usa a ferramenta open_claude_cli para executar. Responde em portugues brasileiro de forma direta e animada.",
        "col": 5.0,
        "row": 6.0,
        "sprite_char": 2,
    },
    {
        "id": "planner",
        "display_name": "Planner",
        "role": "Gerente de Projetos",
        "goal": "Analisar tarefas, decompor em subtarefas e delegar para os agentes mais adequados.",
        "backstory": "Voce e o gerente de projetos da Black Elephant, responsavel por orquestrar os outros agentes e garantir que as tarefas sejam concluidas com eficiencia.",
        "col": 8.0,
        "row": 6.0,
        "sprite_char": 2,
    },
    {
        "id": "designer",
        "display_name": "Designer",
        "role": "UI/UX Designer e Diretor de Arte",
        "goal": "Transformar copy em guia visual (paleta, tipografia, layout, animacoes) para orientar o Dev.",
        "backstory": "Designer de sistemas visuais especializado em sites imersivos Three.js. Traduz emocao em estetica.",
        "col": 2.0,
        "row": 5.0,
        "sprite_char": 3,
    },
    {
        "id": "qa",
        "display_name": "QA",
        "role": "Engenheiro de Qualidade",
        "goal": "Revisar codigo estaticamente e emitir STATUS: APROVADO ou REPROVADO.",
        "backstory": "QA meticuloso. Analisa com checklist e nunca aprova sem evidencia.",
        "col": 5.0,
        "row": 2.0,
        "sprite_char": 2,
    },
    {
        "id": "devops",
        "display_name": "DevOps",
        "role": "Engenheiro DevOps",
        "goal": "Push de projetos aprovados para GitHub e geracao de URL do repositorio.",
        "backstory": "Nunca deixa codigo sem versionamento. Automatizou centenas de pipelines.",
        "col": 9.0,
        "row": 4.0,
        "sprite_char": 2,
    },
    {
        "id": "bibliotecario",
        "display_name": "Bibliotecario",
        "role": "Bibliotecario de Conhecimento",
        "goal": "Organizar outputs no Obsidian ACCESS, atualizar MOCs, padronizar nomes, documentar aprendizados.",
        "backstory": "Arquivista meticuloso do Ideaverse. Qualquer informacao encontrada em segundos.",
        "col": 9.0,
        "row": 6.0,
        "sprite_char": 3,
    },
]

# Campos que devem ser mantidos sincronizados com o código (não inclui col/row/sprite_char)
_AGENT_CONFIG_FIELDS = ["role", "goal", "backstory", "display_name"]

def _ensure_agents_seed(db):
    existing = {r["id"] for r in db.table("agents").select("id").execute().data}
    to_insert = [a for a in AGENT_SEED if a["id"] not in existing]
    if to_insert:
        db.table("agents").insert(to_insert).execute()

def _sync_agent_configs(db):
    """Atualiza role/goal/backstory dos agentes para bater com o código."""
    for agent in AGENT_SEED:
        payload = {k: agent[k] for k in _AGENT_CONFIG_FIELDS if k in agent}
        db.table("agents").update(payload).eq("id", agent["id"]).execute()


_AGENT_DISPLAY = {
    "copywriter":    "Copywriter",
    "vendedor":      "Vendedor",
    "programador":   "Programador",
    "planner":       "Planner",
    "designer":      "Designer",
    "qa":            "QA",
    "devops":        "DevOps",
    "bibliotecario": "Bibliotecario",
}


def _vault_file_path(req: VaultKnowledgeCreate) -> _Path:
    from .obsidian_indexer import VAULT_PATH
    safe = re.sub(r'[<>:"/\\|?*]', "", req.title).strip() or "nota"
    name = _AGENT_DISPLAY.get(req.agent_id, req.agent_id.capitalize())
    v = VAULT_PATH
    t, s = req.ace_type, req.ace_subtype or ""
    if t == "atlas":
        if s == "moc":
            return v / "Atlas" / "Maps" / f"{safe} MOC.md"
        return v / "Atlas" / "Notes" / "Agentes" / name / f"{safe}.md"
    if t == "calendar":
        d = req.date or datetime.date.today().isoformat()
        return v / "Calendar" / f"{d}-{safe}.md"
    if t == "cards":
        return v / "Atlas" / "Notes" / "Cards" / name / f"{safe}.md"
    if t == "efforts":
        folder_map = {"on": "On", "ongoing": "Ongoing", "simmering": "Simmering"}
        folder  = folder_map.get(req.effort_status or "on", "On")
        suffix  = "(OE)" if req.effort_status == "ongoing" else "(E)"
        return v / "Efforts" / folder / f"{safe} {suffix}.md"
    if t == "resources":
        return v / "Atlas" / "Utilities" / name / f"{safe}.md"
    if t == "sources":
        return v / "Atlas" / "Notes" / "Sources" / name / f"{safe}.md"
    return v / "Atlas" / "Notes" / "Agentes" / name / f"{safe}.md"


def _build_frontmatter(req: VaultKnowledgeCreate) -> str:
    today = datetime.date.today().isoformat()
    tags  = list(dict.fromkeys(["agente", req.agent_id] + req.tags))
    up_map = {
        "atlas":     "[[Black Elephant MOC]]",
        "calendar":  "[[Calendar]]",
        "cards":     "[[Atlas]]",
        "efforts":   "[[Efforts]]",
        "resources": "[[Atlas]]",
        "sources":   "[[Atlas]]",
    }
    fm: dict = {
        "up":      [up_map.get(req.ace_type, "[[Black Elephant MOC]]")],
        "agent":   req.agent_id,
        "tags":    tags,
        "created": today,
    }
    if req.rank is not None:
        fm["rank"] = req.rank
    if req.source_url:
        fm["source_url"] = req.source_url
    if req.source_author:
        fm["source_author"] = req.source_author
    return "---\n" + _yaml.dump(fm, allow_unicode=True, default_flow_style=False) + "---\n\n"


@app.get("/api/agents")
def get_agents():
    db = get_supabase()
    result = db.table("agents").select("id,display_name,role,goal,backstory,col,row,sprite_char").execute()
    return result.data


@app.put("/api/agents/{agent_id}")
def update_agent(agent_id: str, update: AgentUpdate):
    db = get_supabase()
    payload = update.model_dump(exclude_unset=True)
    if not payload:
        return {"ok": True}
    db.table("agents").update(payload).eq("id", agent_id).execute()
    return {"ok": True}


class InventoryAction(BaseModel):
    item_id: str
    owner_id: str | None = None

INVENTORY_DEFAULTS = ["sofa", "chair", "desk", "table", "window"]

def _ensure_seed(db):
    result = db.table("inventory_items").select("id").limit(1).execute()
    if not result.data:
        db.table("inventory_items").insert([
            {"item_id": item_id, "quantity": 1, "owner_id": None}
            for item_id in INVENTORY_DEFAULTS
        ]).execute()


@app.get("/api/inventory")
def get_inventory():
    db = get_supabase()
    _ensure_seed(db)
    result = db.table("inventory_items").select("item_id,quantity").is_("owner_id", "null").execute()
    return result.data


@app.post("/api/inventory/add")
def add_inventory(action: InventoryAction):
    db = get_supabase()
    existing = (
        db.table("inventory_items")
        .select("id,quantity")
        .eq("item_id", action.item_id)
        .is_("owner_id", "null")
        .execute()
    )
    if existing.data:
        current = existing.data[0]["quantity"]
        if current >= 4:
            raise HTTPException(status_code=400, detail="Limite de 4 atingido")
        db.table("inventory_items").update({"quantity": current + 1}).eq("id", existing.data[0]["id"]).execute()
    else:
        db.table("inventory_items").insert({"item_id": action.item_id, "quantity": 1, "owner_id": None}).execute()
    return {"ok": True}


@app.post("/api/inventory/remove")
def remove_inventory(action: InventoryAction):
    db = get_supabase()
    existing = (
        db.table("inventory_items")
        .select("id,quantity")
        .eq("item_id", action.item_id)
        .is_("owner_id", "null")
        .execute()
    )
    if not existing.data or existing.data[0]["quantity"] <= 0:
        raise HTTPException(status_code=400, detail="Sem estoque")
    current = existing.data[0]["quantity"]
    db.table("inventory_items").update({"quantity": current - 1}).eq("id", existing.data[0]["id"]).execute()
    return {"ok": True}


@app.get("/api/furniture")
def get_furniture():
    db = get_supabase()
    result = db.table("furniture_placements").select("id,col,row,direction,removed").execute()
    return result.data


@app.post("/api/furniture/save-all")
def save_all_furniture(items: list[FurnitureItem]):
    db = get_supabase()
    payload = [i.model_dump() for i in items]
    db.table("furniture_placements").upsert(payload).execute()
    return {"ok": True, "count": len(items)}


@app.get("/")
def root():
    return {"status": "ok", "service": "be-game-agent-api"}


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Mensagem vazia")

    if req.npc_id == "copywriter":
        agent = create_copywriter()
        task = create_chat_task(agent, req.message)
    elif req.npc_id == "programador":
        agent = create_developer()
        task = create_dev_task(agent, req.message)
    elif req.npc_id == "vendedor":
        agent = create_vendedor()
        task = create_chat_task(agent, req.message)
    elif req.npc_id == "planner":
        agent = create_planner()
        task = create_planner_task(agent, req.message)
    elif req.npc_id == "designer":
        from .agents import create_designer
        agent = create_designer()
        task = create_chat_task(agent, req.message)
    elif req.npc_id == "qa":
        from .agents import create_qa
        agent = create_qa()
        task = create_chat_task(agent, req.message)
    elif req.npc_id == "devops":
        from .agents import create_devops
        agent = create_devops()
        task = create_chat_task(agent, req.message)
    elif req.npc_id == "bibliotecario":
        from .agents import create_bibliotecario
        agent = create_bibliotecario()
        task = create_chat_task(agent, req.message)
    else:
        raise HTTPException(status_code=404, detail=f"NPC sem handler de chat: {req.npc_id}")

    crew = Crew(agents=[agent], tasks=[task], verbose=False)
    result = crew.kickoff()
    return ChatResponse(response=str(result), npc_id=req.npc_id)


@app.post("/api/vault/index")
async def index_vault():
    """Re-indexes the Obsidian vault into Qdrant. Call after vault changes."""
    import asyncio
    from . import obsidian_indexer

    loop = asyncio.get_event_loop()
    count = await loop.run_in_executor(None, obsidian_indexer.run)
    return {"ok": True, "chunks_indexed": count}


@app.get("/api/vault/status")
def vault_status():
    """Returns Qdrant collection stats."""
    try:
        from qdrant_client import QdrantClient
        import os
        client = QdrantClient(url=os.getenv("QDRANT_URL", "http://localhost:6333"))
        collection = os.getenv("QDRANT_COLLECTION", "obsidian_vault")
        info = client.get_collection(collection)
        return {
            "ok": True,
            "collection": collection,
            "points_count": info.points_count,
            "status": str(info.status),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/api/vault/knowledge/{agent_id}")
async def get_vault_knowledge(agent_id: str):
    from . import obsidian_indexer
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, obsidian_indexer.get_agent_files, agent_id)


@app.post("/api/vault/knowledge")
async def create_vault_knowledge(req: VaultKnowledgeCreate):
    from . import obsidian_indexer

    image_link = ""
    if req.image_base64 and req.image_filename:
        img_dir = obsidian_indexer.VAULT_PATH / "Atlas" / "Utilities" / "Images"
        img_dir.mkdir(parents=True, exist_ok=True)
        img_data  = base64.b64decode(req.image_base64)
        img_fname = req.image_filename
        img_path  = img_dir / img_fname
        if img_path.exists():
            stem, ext = _Path(img_fname).stem, _Path(img_fname).suffix
            img_fname = f"{stem}_{int(datetime.datetime.now().timestamp())}{ext}"
            img_path  = img_dir / img_fname
        img_path.write_bytes(img_data)
        image_link = f"\n\n![[{img_fname}]]"

    file_path = _vault_file_path(req)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    if file_path.exists():
        stem      = file_path.stem
        file_path = file_path.parent / f"{stem}_{int(datetime.datetime.now().timestamp())}.md"

    body = _build_frontmatter(req) + f"# {req.title}\n\n{req.content}{image_link}"
    file_path.write_text(body, encoding="utf-8")

    indexed = False
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, obsidian_indexer.index_single_file, file_path)
        indexed = True
    except Exception:
        pass

    return {
        "path":    file_path.relative_to(obsidian_indexer.VAULT_PATH).as_posix(),
        "indexed": indexed,
    }


@app.delete("/api/vault/knowledge")
async def delete_vault_knowledge(req: VaultKnowledgeDelete):
    from . import obsidian_indexer
    file_path = obsidian_indexer.VAULT_PATH / req.path
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(None, obsidian_indexer.delete_file_chunks, file_path)
    except Exception:
        pass
    file_path.unlink()
    return {"deleted": True}


@app.post("/api/vault/image")
async def upload_vault_image(file: UploadFile = File(...)):
    import shutil
    from . import obsidian_indexer
    if file.size and file.size > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Imagem maior que 10MB")
    img_dir = obsidian_indexer.VAULT_PATH / "Atlas" / "Utilities" / "Images"
    img_dir.mkdir(parents=True, exist_ok=True)
    fname    = file.filename or "image.png"
    img_path = img_dir / fname
    if img_path.exists():
        stem, ext = _Path(fname).stem, _Path(fname).suffix
        fname    = f"{stem}_{int(datetime.datetime.now().timestamp())}{ext}"
        img_path = img_dir / fname
    with img_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    return {
        "vault_path":    img_path.relative_to(obsidian_indexer.VAULT_PATH).as_posix(),
        "markdown_link": f"![[{fname}]]",
    }


@app.post("/api/vault/reindex/{agent_id}")
async def reindex_agent_knowledge(agent_id: str):
    from . import obsidian_indexer
    loop  = asyncio.get_event_loop()
    files = await loop.run_in_executor(None, obsidian_indexer.get_agent_files, agent_id)
    count = 0
    for f in files:
        fp = obsidian_indexer.VAULT_PATH / f["path"]
        try:
            n = await loop.run_in_executor(None, obsidian_indexer.index_single_file, fp)
            count += n
        except Exception:
            pass
    return {"indexed_count": count}


@app.get("/api/planner/tasks")
def get_planner_tasks():
    return planner_loop.get_tasks()


@app.post("/api/planner/tasks/{task_id}/cancel")
def cancel_planner_task(task_id: str):
    ok = planner_loop.cancel_task(task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Task nao encontrada ou ja finalizada")
    return {"ok": True}


@app.get("/api/events/stream")
async def events_stream():
    async def generate():
        q = event_bus.subscribe()
        loop = asyncio.get_event_loop()
        yield f"data: {json.dumps({'type': 'connected', 'data': 'Stream de eventos conectado'})}\n\n"
        try:
            while True:
                try:
                    payload = await loop.run_in_executor(
                        None, lambda: q.get(timeout=20)
                    )
                    yield f"data: {payload}\n\n"
                except _queue_mod.Empty:
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            event_bus.unsubscribe(q)
            raise

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
