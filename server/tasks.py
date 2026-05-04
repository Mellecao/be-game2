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


def create_dev_task(agent: Agent, message: str) -> Task:
    return Task(
        description=(
            f"O usuario enviou:\n\n\"{message}\"\n\n"
            f"Siga estes passos:\n"
            f"1. Entenda o que ele quer construir (site, landing page, portfolio, etc.).\n"
            f"2. Derive um project_slug em kebab-case com base no nome do projeto "
            f"   (ex: 'rose-beauty', 'cafe-central', 'advocacia-silva').\n"
            f"3. Monte um prompt completo EM INGLES para o Claude CLI. O prompt deve:\n"
            f"   - Descrever o projeto (nome, segmento, objetivo)\n"
            f"   - Pedir index.html + styles.css + script.js na pasta atual\n"
            f"   - Solicitar site imersivo com Three.js, GSAP ScrollTrigger, "
            f"     Lenis smooth scroll, cursor customizado e microinteracoes\n"
            f"   - Incluir todos os detalhes de copy e visual que o usuario mencionou\n"
            f"4. Use a ferramenta open_claude_cli passando o project_slug e o prompt.\n"
            f"5. Responda em portugues brasileiro confirmando o nome do projeto e a pasta criada."
        ),
        expected_output=(
            "Mensagem em portugues confirmando: nome do projeto, caminho da pasta "
            "e que o Claude CLI foi iniciado para construir o site."
        ),
        agent=agent,
    )
