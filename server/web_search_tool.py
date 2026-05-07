"""DuckDuckGo search tool (sem API key)."""
from __future__ import annotations

from typing import List, Dict
from crewai.tools import BaseTool
from pydantic import Field

from duckduckgo_search import DDGS


class WebSearchTool(BaseTool):
    name: str = "web_search"
    description: str = (
        "Busca na web via DuckDuckGo. Recebe uma query e retorna lista de "
        "{url, title, snippet}. Use para encontrar competidores e referencias."
    )
    max_results: int = Field(default=10)

    def _run(self, query: str) -> List[Dict[str, str]]:
        out: List[Dict[str, str]] = []
        with DDGS() as ddgs:
            results = ddgs.text(query, max_results=self.max_results)
        for r in results:
            out.append({
                "url": r.get("href", ""),
                "title": r.get("title", ""),
                "snippet": r.get("body", ""),
            })
        return out
