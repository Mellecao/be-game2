from crewai import Task, Agent


def create_trello_review_task(agent: Agent) -> Task:
    return Task(
        description=(
            "Use a ferramenta 'trello_list_cards' para buscar todos os cards da lista TO-DO no Trello. "
            "Para cada card encontrado:\n"
            "1. Informe o nome do card\n"
            "2. Explique o que está sendo solicitado\n"
            "3. Liste as restrições ou detalhes importantes mencionados\n"
            "Se não houver cards, informe que a lista está vazia."
        ),
        expected_output=(
            "Relatório listando cada card do Trello com: nome, solicitação identificada e detalhes relevantes."
        ),
        agent=agent,
    )


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
