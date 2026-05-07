from __future__ import annotations

import json

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
            f"## Paleta de Cores\n- Primaria: #XXXXXX (nome)\n- Secundaria: #XXXXXX\n"
            f"- Accent: #XXXXXX\n- Background: #XXXXXX\n- Texto: #XXXXXX\n\n"
            f"## Tipografia\n- Heading: [Google Font]\n- Body: [Google Font]\n\n"
            f"## Mood & Estetica\n- Palavras-chave: ...\n\n"
            f"## Layout por Secao\n- Hero: ...\n- Features: ...\n- CTA: ...\n\n"
            f"## Animacoes GSAP Sugeridas\n- ...\n\n"
            f"## Assets Necessarios\n- ...\n\n"
            f"4. Ao FINAL do markdown, anexe um bloco asset_manifest com este formato EXATO:\n\n"
            f"```asset_manifest\n"
            f"{{\n"
            f"  \"images\": [\n"
            f"    {{\"id\": \"hero\", \"prompt_pt\": \"...\", \"purpose\": \"...\", "
            f"\"width\": 1920, \"height\": 1080, \"convert_to_3d\": false}},\n"
            f"    {{\"id\": \"logo\", \"prompt_pt\": \"...\", \"purpose\": \"...\", "
            f"\"width\": 1024, \"height\": 1024, \"convert_to_3d\": true}}\n"
            f"  ]\n"
            f"}}\n"
            f"```\n\n"
            f"O bloco asset_manifest e OBRIGATORIO. Liste de 2 a 5 imagens. "
            f"Marque convert_to_3d=true apenas para itens que fazem sentido como modelo 3D "
            f"(logo, mascote, produto). Backgrounds e fotos fica false."
        ),
        expected_output=f"Guia visual completo em Markdown comecando com '# Guia Visual: {slug}' incluindo bloco asset_manifest.",
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
            f"A ferramenta ira: git init → add → commit → criar repo no GitHub → push → deploy no Netlify.\n\n"
            f"Retorne EXATAMENTE o texto retornado pela ferramenta, que sera no formato:\n"
            f"github: https://github.com/username/{slug}\n"
            f"netlify: https://{slug}.netlify.app\n\n"
            f"Nao adicione texto antes ou depois."
        ),
        expected_output=(
            f"Duas linhas: 'github: <URL>' e 'netlify: <URL>'"
        ),
        agent=agent,
    )


def create_dev_revision_task(agent: Agent, context: dict) -> Task:
    return Task(
        description=(
            f"O QA REPROVOU o projeto '{context['slug']}'. Voce precisa corrigir os problemas encontrados.\n\n"
            f"Relatorio do QA:\n{context['qa_feedback']}\n\n"
            f"A pasta do projeto ja existe em: {context['project_dir']}\n\n"
            f"Siga estes passos:\n"
            f"1. Use o mesmo project_slug '{context['slug']}' (a pasta ja existe com os arquivos).\n"
            f"2. Monte um prompt de REVISAO em ingles para o Claude CLI. O prompt deve:\n"
            f"   - Informar que e uma revisao de projeto existente\n"
            f"   - Listar cada problema identificado pelo QA e pedir correcao\n"
            f"   - Solicitar que Claude leia os arquivos atuais antes de editar\n"
            f"   - Garantir que index.html tenha <!DOCTYPE html>, meta charset, meta viewport e <title>\n"
            f"   - Garantir presenca de CDN links para Three.js e/ou GSAP\n"
            f"   - Incluir ao final: criar arquivo .claude-done com conteudo 'done'\n"
            f"3. Use a ferramenta open_claude_cli com o project_slug '{context['slug']}' e o prompt de revisao.\n"
            f"4. Confirme em portugues que a revisao foi iniciada e quais problemas serao corrigidos."
        ),
        expected_output=(
            "Confirmacao em portugues de que o Claude CLI foi iniciado para revisao, "
            "com lista dos problemas que serao corrigidos."
        ),
        agent=agent,
    )


def create_planner_close_task(agent: Agent, context: dict) -> Task:
    netlify_line = f"\nNetlify: {context['netlify_url']}" if context.get("netlify_url") else ""
    return Task(
        description=(
            f"Voce e o Planner. O projeto '{context['card_name']}' foi concluido!\n\n"
            f"GitHub: {context['github_url']}{netlify_line}\n\n"
            f"Confirme a entrega em 2-3 frases: o que foi entregue, onde esta "
            f"(GitHub e Netlify) e que o card no Trello foi movido para Concluido."
        ),
        expected_output="Confirmacao da entrega em 2-3 frases com as URLs do GitHub e Netlify.",
        agent=agent,
    )


def create_image_pipeline_task(agent: Agent, context: dict) -> Task:
    slug = context["slug"]
    manifest_json = json.dumps(context["manifest"], ensure_ascii=False, indent=2)
    return Task(
        description=(
            f"Voce e o Image Artist. Gere as imagens do projeto '{slug}'.\n\n"
            f"Manifest recebido:\n{manifest_json}\n\n"
            f"Para CADA item em images:\n"
            f"1. Reescreva o prompt_pt como um prompt detalhado em INGLES (>= 30 palavras: "
            f"   assunto, estilo, iluminacao, composicao, qualidade tipo 'cinematic', '8k', 'sharp focus').\n"
            f"2. Chame flux_image passando esse prompt em ingles.\n"
            f"3. Guarde o caminho retornado.\n\n"
            f"Ao final, responda em portugues com uma tabela:\n"
            f"| id | png_path | prompt usado |\n"
            f"|---|---|---|"
        ),
        expected_output=(
            "Tabela em portugues com id, png_path, prompt em ingles para cada imagem do manifest."
        ),
        agent=agent,
    )


def create_3d_pipeline_task(agent: Agent, context: dict) -> Task:
    slug = context["slug"]
    return Task(
        description=(
            f"Voce e o 3D Artist. O Image Artist ja gerou PNGs do projeto '{slug}'.\n\n"
            f"O manifest_resolved esta em output/{slug}/assets/manifest_resolved.json.\n\n"
            f"1. Filtre apenas itens com convert_to_3d=true E que tenham png_path valido.\n"
            f"2. Para cada um, chame hunyuan3d_generate passando image_path=png_path absoluto.\n"
            f"3. Capture o glb_path retornado.\n\n"
            f"Ao final, responda em portugues com tabela:\n"
            f"| id | glb_path | source_png |\n|---|---|---|"
        ),
        expected_output=(
            "Tabela em portugues com id, glb_path, source_png para cada modelo 3D gerado."
        ),
        agent=agent,
    )


def create_designer_review_task(agent: Agent, context: dict) -> Task:
    slug = context["slug"]
    manifest_resolved_json = json.dumps(context["manifest_resolved"], ensure_ascii=False, indent=2)
    guide_excerpt = context.get("guide_excerpt", "")
    return Task(
        description=(
            f"Voce e o Designer revisando os PNGs do projeto '{slug}'.\n\n"
            f"Trecho do guia visual:\n{guide_excerpt[:2000]}\n\n"
            f"Manifest resolvido:\n{manifest_resolved_json}\n\n"
            f"Para cada imagem com png_path, examine visualmente (voce esta recebendo via "
            f"vision LLM, com a imagem anexada na mensagem) e julgue:\n"
            f"- Atende ao 'purpose' declarado?\n- Bate com o mood do guia?\n"
            f"- Qualidade tecnica aceitavel?\n\n"
            f"Responda APENAS um JSON valido neste formato:\n"
            f"{{\n"
            f"  \"reviews\": [\n"
            f"    {{\"id\": \"...\", \"verdict\": \"APROVADO\" ou \"REPROVADO\", "
            f"\"reason\": \"...\", \"regen_prompt\": \"...\" (apenas se REPROVADO)}}\n"
            f"  ]\n"
            f"}}\n"
            f"NADA fora do JSON. Sem markdown, sem texto antes ou depois."
        ),
        expected_output="JSON estrito com chave 'reviews' contendo verdict, reason e regen_prompt por imagem.",
        agent=agent,
    )


def create_curator_finalize_task(agent: Agent, context: dict) -> Task:
    slug = context["slug"]
    return Task(
        description=(
            f"Voce e o Bibliotecario fazendo curadoria final do projeto '{slug}'.\n\n"
            f"Status final do pipeline: {context['final_status']}\n"
            f"MOC: {context['moc_path']}\n"
            f"Effort: {context['effort_path']}\n\n"
            f"Passos obrigatorios:\n"
            f"1. Use pipeline_log com slug='{slug}' para listar tudo que foi feito.\n"
            f"2. Use vault_organize op=list para inspecionar a estrutura ACE atual:\n"
            f"   - Atlas/Maps, Atlas/Notes, Atlas/Utilities (sub-pastas por agente)\n"
            f"   - Calendar/\n"
            f"   - Efforts/On|Ongoing|Simmering|Archives\n"
            f"3. Para cada arquivo escrito (eventos vault_write):\n"
            f"   - Esta no bucket ACE correto? Se nao, vault_organize op=move.\n"
            f"   - E uma duplicata/draft? Se sim, vault_organize op=delete (com reason).\n"
            f"4. Identifique e apague:\n"
            f"   - Arquivos com mesmo titulo no mesmo bucket (mantenha o mais recente).\n"
            f"   - Notas com conteudo < 50 chars (excluindo frontmatter).\n"
            f"   - NUNCA apague nada de output/{slug}/ — esses vao pro git.\n"
            f"5. Atualize o MOC ({context['moc_path']}) acrescentando secao '## Curadoria' "
            f"   com bullets do que foi consolidado e do que foi removido (com motivo).\n"
            f"6. Escreva uma nota final em "
            f"   'Atlas/Notes/Agentes/Bibliotecario/{slug}-curation.md' "
            f"   com summary executivo do projeto (use vault_organize ou vault_writer).\n\n"
            f"Responda em portugues com resumo curto: arquivos movidos (N), apagados (N), MOC atualizado, "
            f"nota de curadoria criada em <path>."
        ),
        expected_output=(
            "Resumo em portugues: contagem de arquivos movidos/apagados, confirmacao de MOC atualizado e path da nota de curadoria."
        ),
        agent=agent,
    )


def create_creative_brief_task(context: dict) -> Task:
    slug = context["slug"]
    card_name = context.get("card_name", "")
    card_desc = context.get("card_desc", "")
    return Task(
        description=(
            f"Voce e o Diretor Criativo. Entregue bundle pronto pro Dev do projeto '{slug}'.\n\n"
            f"Card: {card_name}\nBriefing: {card_desc}\n\n"
            f"Sequencia sugerida (ajuste se necessario):\n"
            f"1. Researcher monta dossie (5 refs awwwards/dribbble/behance + 5 competidores) "
            f"   e salva em output/{slug}/research/references.json com campo 'frankenstein'.\n"
            f"2. Copywriter le references.json e escreve copy alinhado ao tom do Frankenstein. "
            f"   Salva em vault.\n"
            f"3. Designer le references.json + copy, gera asset_manifest com mood baseado nas refs. "
            f"   Salva guia visual em vault.\n"
            f"4. Image Artist chama generate_all_images uma unica vez (passa o manifest path).\n"
            f"5. 3D Artist chama generate_all_glbs se houver itens com convert_to_3d=true.\n"
            f"6. Designer Reviewer aprova ou solicita regen. Pode haver 1 retry maximo.\n\n"
            f"Reordene se algum passo bloquear. Conclua quando manifest_resolved.json estiver "
            f"completo e o review aprovar."
        ),
        expected_output=(
            f"JSON: {{\"status\": \"ready\", "
            f"\"manifest_resolved_path\": \"output/{slug}/assets/manifest_resolved.json\", "
            f"\"references_path\": \"output/{slug}/research/references.json\"}}"
        ),
    )


def create_qa_brief_task(context: dict) -> Task:
    slug = context["slug"]
    project_dir = context["project_dir"]
    references_path = context.get("references_path", "")
    return Task(
        description=(
            f"Voce e o Lead QA do projeto '{slug}'.\n\n"
            f"Project dir: {project_dir}\n"
            f"References: {references_path}\n\n"
            f"Sequencia:\n"
            f"1. QA-codigo revisa arquivos do projeto. Se REPROVADO, encerra com lista de issues.\n"
            f"2. Se APROVADO, QA-visual:\n"
            f"   a. server_runner: sobe servidor de {project_dir}, pega URL\n"
            f"   b. browser_qa: tira screenshots multi-viewport (desktop/tablet/mobile) "
            f"      e por secao em output/{slug}/qa_visual/current/\n"
            f"   c. visual_diff: compara cada secao current vs ref correspondente "
            f"      do Frankenstein em {references_path}\n"
            f"   d. teardown do server_runner OBRIGATORIO mesmo em erro\n"
            f"3. Se houver REPROVADO, redija output/{slug}/qa_visual/fix_prompt.md "
            f"   agregando issues de codigo + visuais. Markdown estruturado por secao "
            f"   com refs concretos (px, hex, paths de screenshots).\n"
            f"4. Devolva veredicto final: APROVADO | REPROVADO."
        ),
        expected_output=(
            "JSON estrito: {\"verdict\": \"APROVADO\"|\"REPROVADO\", "
            "\"report_path\": \"...\", \"fix_prompt_path\": \"...\" (se REPROVADO)}"
        ),
    )
