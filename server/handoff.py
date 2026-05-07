"""Gera mensagem curta de handoff entre agentes via LLM."""
from __future__ import annotations

from functools import lru_cache


def _call_llm(prompt: str) -> str:
    """Chama o llm global. Isolado em func separada pra ser mockavel."""
    from .agents import llm
    return llm.call(messages=[{"role": "user", "content": prompt}])


@lru_cache(maxsize=128)
def _generate_cached(agent_id: str, agent_name: str, what_summary: str, next_agent: str) -> str:
    prompt = (
        f"Voce e o {agent_name}. Acabou de entregar: {what_summary}.\n"
        f"Proximo agente: {next_agent or '(fim do pipeline)'}.\n"
        f"Em 1 frase <= 120 caracteres, em portugues coloquial, anuncie o que entregou "
        f"e pra quem passa. Sem meta-comentario, sem aspas."
    )
    try:
        out = _call_llm(prompt).strip()
        return out[:140]
    except Exception:
        return _fallback(agent_name, next_agent or "")


def _fallback(agent_name: str, next_agent: str) -> str:
    if next_agent:
        return f"{agent_name} terminou. Passando pro {next_agent}."
    return f"{agent_name} terminou."


def generate_handoff(agent_id: str, agent_name: str, what_was_done: str, next_agent: str | None) -> str:
    """Gera mensagem curta de transicao via LLM. Cacheia por hash do input."""
    return _generate_cached(agent_id, agent_name, what_was_done[:200], next_agent or "")
