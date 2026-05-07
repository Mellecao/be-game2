"""Tool CrewAI para o bibliotecario ler o pipeline log de uma task."""
from __future__ import annotations

import json

from crewai.tools import BaseTool

from . import pipeline_logger


class PipelineLogTool(BaseTool):
    name: str = "pipeline_log"
    description: str = (
        "Le todos os eventos do pipeline log de um projeto. Argumento: slug (string, "
        "kebab-case do projeto). Retorna lista JSON com eventos {ts, event, ...payload}. "
        "Use para entender o que cada agente fez antes de decidir reorganizar."
    )

    def _run(self, slug: str) -> str:
        events = pipeline_logger.read_log(slug)
        return json.dumps(events, ensure_ascii=False)
