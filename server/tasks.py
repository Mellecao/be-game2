from __future__ import annotations

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


def create_planner_task(agent: Agent, message: str) -> Task:
    return Task(
        description=(
            f"O usuario enviou:\n\n\"{message}\"\n\n"
            f"Se a mensagem envolver tarefas, Trello, pendencias ou 'o que tem para fazer', "
            f"use a ferramenta trello_list_cards para buscar os cards da lista TO-DO "
            f"e explique cada card: o que foi solicitado e detalhes importantes. "
            f"Se for outra pergunta, responda como gerente de projetos ajudaria."
        ),
        expected_output="Resposta em portugues brasileiro, clara e objetiva.",
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


def create_planner_moc_task(agent: Agent, context: dict) -> Task:
    return Task(
        description=(
            f"O pipeline iniciou para o projeto '{context['slug']}'.\n\n"
            f"Card: {context['card_name']}\n"
            f"Briefing: {context.get('card_desc', '(sem descricao)')}\n\n"
            f"Um MOC de projeto foi criado em '{context['moc_path']}' e uma nota de "
            f"Effort em '{context['effort_path']}'. "
            f"Confirme em 1 frase que o planejamento foi iniciado e que os agentes serao acionados."
        ),
        expected_output="Confirmacao em 1 frase de que o planejamento foi iniciado.",
        agent=agent,
    )


def create_copywriter_pipeline_task(agent: Agent, context: dict) -> Task:
    return Task(
        description=(
            f"Voce e o Copywriter. Escreva a copy COMPLETA para o projeto abaixo.\n\n"
            f"Projeto: {context['card_name']}\n"
            f"Briefing: {context.get('card_desc', '(sem descricao)')}\n\n"
            f"Use obsidian_vault_search para buscar tom de voz da Black Elephant e "
            f"exemplos de copy aprovados antes de escrever.\n\n"
            f"Estruture em Markdown com estas secoes obrigatorias:\n"
            f"# Headline\n## Subheadline\n## Hero\n## Beneficios (3-5)\n"
            f"## Como Funciona\n## CTA\n## FAQ (3 perguntas)\n\n"
            f"Escreva em portugues brasileiro, persuasivo e direto."
        ),
        expected_output=(
            "Copy completa em Markdown com todas as secoes: Headline, Subheadline, "
            "Hero, Beneficios, Como Funciona, CTA, FAQ."
        ),
        agent=agent,
    )


def create_designer_task(agent: Agent, context: dict) -> Task:
    slug = context['slug']
    return Task(
        description=(
            f"Voce e o Designer. A copy do projeto '{slug}' foi salva.\n\n"
            f"1. Use obsidian_vault_search para buscar: '{slug} copy'\n"
            f"2. Leia o conteudo encontrado\n"
            f"3. Crie um guia visual completo em Markdown:\n\n"
            f"# Guia Visual: {slug}\n\n"
            f"## Paleta de Cores\n"
            f"- Primaria: #XXXXXX (nome)\n- Secundaria: #XXXXXX\n"
            f"- Accent: #XXXXXX\n- Background: #XXXXXX\n- Texto: #XXXXXX\n\n"
            f"## Tipografia\n"
            f"- Heading: [Google Font] — tamanhos h1/h2/h3\n"
            f"- Body: [Google Font] — tamanho padrao\n\n"
            f"## Mood & Estetica\n"
            f"- Palavras-chave: (ex: dark, imersivo, organico, minimalista)\n\n"
            f"## Layout por Secao\n"
            f"- Hero: (descricao layout)\n- Features: ...\n- CTA: ...\n\n"
            f"## Animacoes GSAP Sugeridas\n"
            f"- (lista de animacoes com propriedades)\n\n"
            f"## Assets Necessarios\n"
            f"- (imagens, icones, videos)\n\n"
            f"Retorne APENAS o Markdown do guia, comecando com '# Guia Visual: {slug}'."
        ),
        expected_output=f"Guia visual completo em Markdown comecando com '# Guia Visual: {slug}'",
        agent=agent,
    )


def create_qa_task(agent: Agent, context: dict) -> Task:
    return Task(
        description=(
            f"Voce e o QA. O Dev concluiu o projeto '{context['slug']}' em: {context['project_dir']}\n\n"
            f"Arquivos encontrados:\n{context.get('file_summary', '(nenhum arquivo listado)')}\n\n"
            f"Faca a revisao estatica com este checklist:\n\n"
            f"1. [ ] index.html existe e contem <!DOCTYPE html>\n"
            f"2. [ ] <meta charset='UTF-8'> presente\n"
            f"3. [ ] <meta name='viewport'> presente\n"
            f"4. [ ] <title> nao esta vazio\n"
            f"5. [ ] CDN links para Three.js e/ou GSAP presentes\n"
            f"6. [ ] Nenhum texto hardcoded em ingles visivel ao usuario final\n"
            f"7. [ ] Arquivo styles.css ou equivalente existe\n"
            f"8. [ ] Arquivo JS/TS principal existe\n\n"
            f"Para cada item: OK (aprovado) ou FALHOU (reprovado) com motivo.\n\n"
            f"Na ultima linha escreva EXATAMENTE:\n"
            f"'STATUS: APROVADO' se todos os itens criticos (1-5) passaram, "
            f"ou 'STATUS: REPROVADO — [motivos]' caso contrario."
        ),
        expected_output=(
            "Checklist de QA com OK/FALHOU por item e STATUS: APROVADO ou STATUS: REPROVADO na ultima linha."
        ),
        agent=agent,
    )


def create_devops_task(agent: Agent, context: dict) -> Task:
    slug = context['slug']
    return Task(
        description=(
            f"Voce e o DevOps. O QA aprovou o projeto '{slug}'.\n\n"
            f"Use a ferramenta github_push passando:\n"
            f"  project_slug: '{slug}'\n\n"
            f"A ferramenta ira: git init → add → commit → criar repo no GitHub → push.\n\n"
            f"Retorne APENAS a URL do repositorio GitHub retornada pela ferramenta, "
            f"no formato: https://github.com/username/repo-name\n"
            f"Nao adicione texto antes ou depois da URL."
        ),
        expected_output="URL GitHub no formato https://github.com/username/nome-do-repo",
        agent=agent,
    )


def create_planner_close_task(agent: Agent, context: dict) -> Task:
    return Task(
        description=(
            f"Voce e o Planner. O projeto '{context['card_name']}' foi concluido!\n\n"
            f"GitHub: {context['github_url']}\n\n"
            f"Confirme a entrega em 2-3 frases: o que foi entregue, onde esta e "
            f"que o card no Trello foi movido para Concluido."
        ),
        expected_output="Confirmacao da entrega em 2-3 frases com a URL do GitHub.",
        agent=agent,
    )
