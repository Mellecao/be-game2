from crewai import Task, Agent


def create_chat_task(agent: Agent, message: str) -> Task:
    return Task(
        description=(
            f"O usuario enviou a seguinte mensagem no chat:\n\n"
            f"\"{message}\"\n\n"
            f"Responda de forma natural e util, em portugues brasileiro. "
            f"Se for um briefing pedindo copy de landing page, gere a copy "
            f"completa em Markdown (headline, subheadline, hero, beneficios, "
            f"como funciona, CTA, FAQ). Caso contrario, responda conversacionalmente "
            f"como um copywriter ajudaria."
        ),
        expected_output="Resposta em portugues brasileiro, util e direta.",
        agent=agent,
    )
