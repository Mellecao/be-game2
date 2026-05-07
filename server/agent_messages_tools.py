"""Tools usadas pelo agente Secretario pra ler estado do pipeline + historico."""
from __future__ import annotations

from datetime import datetime
from crewai.tools import BaseTool
from pydantic import Field

from . import agent_messages


def _get_tasks_fn():
    """Indireto pra ser mockavel em testes."""
    from .planner_loop import get_tasks
    return get_tasks()


class GetPipelineStatusTool(BaseTool):
    name: str = "get_pipeline_status"
    description: str = (
        "Retorna status compacto do pipeline atual: cards ativos, em que step cada um esta, "
        "e log curto. Use quando o usuario perguntar 'como esta o pipeline' ou 'o que esta rodando'."
    )

    def _run(self) -> str:
        tasks = _get_tasks_fn()
        if not tasks:
            return "Nenhum card ativo no momento."
        lines = []
        for t in tasks:
            card = t.get("card_name", "?")
            status = t.get("status", "?")
            step = t.get("step", 0)
            log = t.get("log", "")[:80]
            lines.append(f"- '{card}' (step {step}, status={status}): {log}")
        return f"{len(tasks)} card(s) ativo(s):\n" + "\n".join(lines)


class GetActiveTasksTool(BaseTool):
    name: str = "get_active_tasks"
    description: str = (
        "Lista nomes e status dos cards em execucao. Use quando o usuario "
        "perguntar 'quantos projetos rodando' ou 'quais cards'."
    )

    def _run(self) -> str:
        tasks = _get_tasks_fn()
        if not tasks:
            return "Sem cards ativos."
        active = [t for t in tasks if t.get("status") not in ("done", "error", "qa_blocked", "cancelled")]
        return f"{len(active)} card(s) em execucao: " + ", ".join(t.get("card_name", "?") for t in active)


class GetAgentHistoryTool(BaseTool):
    name: str = "get_agent_history"
    description: str = (
        "Retorna ultimas mensagens de um agente especifico. Use quando o usuario "
        "perguntar 'o que o Researcher disse' ou 'historico do Designer'. "
        "agent_id: id do agente (ex: researcher, designer, dev)."
    )
    limit: int = Field(default=20)

    def _run(self, agent_id: str, limit: int = 20) -> str:
        msgs = agent_messages.history(agent_id, limit=limit)
        if not msgs:
            return f"(sem mensagens) registradas pra {agent_id}"
        lines = []
        for m in msgs[-limit:]:
            ts_str = datetime.fromtimestamp(m["ts"]).strftime("%H:%M")
            lines.append(f"[{ts_str}] ({m['type']}) {m['text']}")
        return "\n".join(lines)
