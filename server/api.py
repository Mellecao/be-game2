import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from crewai import Crew
from dotenv import load_dotenv

from .agents import create_copywriter
from .tasks import create_chat_task
from .supabase_client import get_supabase

load_dotenv()

app = FastAPI(title="BE-Game Agent API")

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

AGENT_SEED = [
    {
        "id": "copywriter",
        "display_name": "Copywriter",
        "role": "Copywriter de Landing Pages",
        "goal": "Conversar com o usuario para entender briefings de landing pages e gerar textos persuasivos quando solicitado.",
        "backstory": "Voce e um copywriter senior da Black Elephant, especializado em landing pages para empresas de tecnologia.",
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
        "role": "Desenvolvedor Full-Stack",
        "goal": "Implementar solucoes tecnicas de alta qualidade para os projetos da empresa.",
        "backstory": "Voce e um desenvolvedor senior da Black Elephant com expertise em TypeScript, Python e integrações de API.",
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
]

def _ensure_agents_seed(db):
    result = db.table("agents").select("id").limit(1).execute()
    if not result.data:
        db.table("agents").insert(AGENT_SEED).execute()


@app.get("/api/agents")
def get_agents():
    db = get_supabase()
    _ensure_agents_seed(db)
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

    if req.npc_id != "copywriter":
        raise HTTPException(status_code=404, detail=f"NPC desconhecido: {req.npc_id}")

    agent = create_copywriter()
    task = create_chat_task(agent, req.message)
    crew = Crew(agents=[agent], tasks=[task], verbose=False)

    result = crew.kickoff()
    return ChatResponse(response=str(result), npc_id=req.npc_id)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
