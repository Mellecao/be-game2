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
