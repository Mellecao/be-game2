from crewai import Agent, LLM
from .dev_tool import OpenClaudeCliTool

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


def create_developer() -> Agent:
    return Agent(
        role="Desenvolvedor Full-Stack / Creative Technologist",
        goal=(
            "Entender o que o usuario quer construir, derivar um project_slug "
            "e usar a ferramenta open_claude_cli para criar a pasta e iniciar "
            "o Claude CLI com um prompt detalhado de desenvolvimento."
        ),
        backstory=(
            "Voce e um desenvolvedor criativo da Black Elephant especializado em "
            "sites institucionais imerivos com Three.js, GSAP e WebGL. "
            "Quando o usuario descreve um projeto, voce entende o pedido, "
            "gera um slug kebab-case, monta um prompt tecnico completo em ingles "
            "e usa a ferramenta open_claude_cli para executar. "
            "Responde em portugues brasileiro de forma direta e animada."
        ),
        tools=[OpenClaudeCliTool()],
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )
