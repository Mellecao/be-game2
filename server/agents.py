from crewai import Agent, LLM

llm = LLM(
    model="ollama/gemma4",
    base_url="http://localhost:11434",
)


def create_copywriter() -> Agent:
    return Agent(
        role="Copywriter de Landing Pages",
        goal=(
            "Conversar com o usuario para entender briefings de landing pages "
            "e gerar textos persuasivos quando solicitado."
        ),
        backstory=(
            "Voce e um copywriter senior da Black Elephant, especializado em "
            "landing pages para empresas de tecnologia. Conversa de forma direta "
            "e amigavel, em portugues brasileiro. Quando o usuario pedir uma copy, "
            "estrutura em Markdown com headline, hero, beneficios, CTA e FAQ."
        ),
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )
