"""
ObsidianVaultTool — CrewAI BaseTool que faz busca semântica no vault Obsidian via Qdrant.

Cada agente que receber essa ferramenta pode consultar o conhecimento da empresa
(Black Elephant) e do BE-Game diretamente nas notas do Obsidian.
"""
from __future__ import annotations

import os
from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from qdrant_client import QdrantClient

QDRANT_URL     = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
COLLECTION     = os.getenv("QDRANT_COLLECTION", "obsidian_vault")
EMBED_MODEL = "BAAI/bge-small-en-v1.5"
TOP_K       = 5          # resultados por busca
SCORE_MIN   = 0.35       # descarta chunks com similaridade baixa


class _Input(BaseModel):
    query: str = Field(description="Pergunta ou tema para buscar nas notas do Obsidian")


class ObsidianVaultTool(BaseTool):
    name: str = "obsidian_vault_search"
    description: str = (
        "Busca semântica no vault Obsidian da Black Elephant. "
        "Use quando precisar de informações sobre a empresa, serviços, tom de voz, "
        "clientes, processos, copies aprovadas ou detalhes do BE-Game. "
        "Retorna trechos das notas mais relevantes para a pergunta."
    )
    args_schema: Type[BaseModel] = _Input

    def _run(self, query: str) -> str:
        try:
            from fastembed import TextEmbedding

            model  = TextEmbedding(model_name=EMBED_MODEL)
            vector = next(iter(model.embed([query]))).tolist()

            client  = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, check_compatibility=False)
            response = client.query_points(
                collection_name=COLLECTION,
                query=vector,
                limit=TOP_K,
                score_threshold=SCORE_MIN,
                with_payload=True,
            )
            results = response.points

            if not results:
                return "Nenhuma nota relevante encontrada no vault para esta busca."

            parts: list[str] = []
            for r in results:
                p     = r.payload or {}
                path  = p.get("path", "")
                sec   = p.get("section", "")
                title = p.get("title", path)
                label = f"{title} › {sec}" if sec else title
                raw   = p.get("content", f"(ver nota: {path})")
                score = f"{r.score:.2f}"
                parts.append(f"**[{label}]** _(relevância: {score})_\n{raw}")

            return "\n\n---\n\n".join(parts)

        except Exception as e:
            return f"Erro ao consultar o vault: {e}"


# ── Singleton para reusar o modelo embeddo ────────────────────────────────────

_tool_instance: ObsidianVaultTool | None = None


def get_vault_tool() -> ObsidianVaultTool:
    global _tool_instance
    if _tool_instance is None:
        _tool_instance = ObsidianVaultTool()
    return _tool_instance
