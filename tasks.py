from crewai import Task, Agent


def create_landing_page_task(agent: Agent, briefing: str) -> Task:
    return Task(
        description=(
            f"Com base no briefing abaixo, crie a copy completa de uma landing page.\n\n"
            f"BRIEFING:\n{briefing}\n\n"
            f"A saída DEVE ser em Markdown estruturado com as seguintes seções:\n"
            f"- Headline principal\n"
            f"- Subheadline\n"
            f"- Seção Hero (texto de abertura)\n"
            f"- Benefícios (3 a 5 itens)\n"
            f"- Como funciona (passos)\n"
            f"- Call to Action (CTA)\n"
            f"- FAQ (3 perguntas)\n\n"
            f"Escreva tudo em português brasileiro. Seja persuasivo e direto."
        ),
        expected_output=(
            "Documento Markdown completo com todas as seções da landing page: "
            "headline, subheadline, hero, benefícios, como funciona, CTA e FAQ."
        ),
        agent=agent,
    )
