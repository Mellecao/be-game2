# Manager Hierárquico + Researcher + QA Visual + Bibliotecário com Julgamento

**Data:** 2026-05-07
**Autor:** brainstorming session com guilherme@blackelephant.com.br
**Estado:** design aprovado, aguardando review do user antes do plano de implementação

## 1. Contexto e motivação

O pipeline atual do `planner_loop.py` é uma sequência rígida de 10 etapas determinísticas (Planner → Copy → Design → Image → 3D → Review → Dev → QA → Deploy → Closing). Isso funciona bem mas tem 3 limitações:

1. **Sem inteligência de orquestração:** se o copy descola do design, ou se o QA reprova por motivo X, o pipeline não tem quem decida re-rodar uma etapa específica ou reordenar.
2. **Sem pesquisa de referências:** o Designer monta o briefing visual com base apenas no card do Trello e em conhecimento do LLM, sem consultar o estado-da-arte do segmento (awwwards/dribbble/behance) nem competidores diretos.
3. **QA superficial:** o QA atual é text-based — lê o código mas nunca **vê** o site renderizado. Bugs visuais (espaçamento, hierarquia tipográfica, contraste de CTA) passam direto.

Este spec adiciona 3 capacidades:

1. **Manager LLM** (CrewAI `Process.hierarchical`) em dois Crews (Criativo e QA) que decidem ordem, redirecionamentos e fix prompts.
2. **Researcher** que monta dossiê com 10+ referências (5 inspiracionais top awwwards/dribbble/behance + 5 concorrentes diretos), com screenshots por seção e proposta de "Frankenstein" (melhor hero de qual ref + melhor seção 2 de qual ref).
3. **QA Visual** com browser automation: sobe o servidor, navega com Playwright, tira prints multi-viewport, compara com referências via vision LLM, e redige fix_prompt acionável quando reprova.

E refina o **Bibliotecário** existente: ele continua sendo o ponto único de escrita no vault Obsidian, mas agora julga (via LLM) o que é conhecimento novo vs ruído antes de indexar no Qdrant.

## 2. Decisões de arquitetura

| Decisão | Escolha | Razão |
|---|---|---|
| Padrão Manager | `Process.hierarchical` nativo do CrewAI | Built-in, less code, manager_llm decide delegação automática |
| Quantos Crews | 2 (Criativo + QA), não 1 único | Crew Criativo termina antes do Dev rodar (Claude CLI). Crew QA só inicia depois do Dev. Isolamento limpo. |
| Lugar do Researcher | Antes do Copywriter | Referências informam o tom da copy E o design; mesmo dossiê fica acessível pro QA-visual comparar |
| Profundidade do research | 10+ sites (5 inspiracionais + 5 concorrentes) | User explicitamente pediu "análise de competidores e padrões de mercado" |
| QA | Dois em sequência: QA-código (atual) + QA-visual (novo) | Pega bugs de código E de UX. QA-visual só roda se QA-código aprovar. |
| Browser tooling | Playwright (sync API + stealth) | Awwwards tem anti-bot; Playwright stealth resolve. Mesmo runtime serve pro Researcher e pro QA-visual. |
| Iteração QA | Máximo 2 retries no Dev | Após 3 reprovações totais, marca card como `qa_blocked` e alerta. Sem loop infinito. |
| Determinismo nas tools caras | Image Artist e 3D Artist mantêm tools agregadas (`generate_all_images`, `generate_all_glbs`) que internamente fazem for-loop sequencial | Evita Manager LLM rechamar geração por engano. Semáforo no `FluxImageTool` já garante 1 req/vez no Forge. |
| Bibliotecário | Stub atual + nova função `judge_artifact()` LLM-based | Operacional sempre escrito; conhecimento gated por julgamento pra evitar poluir Qdrant |

## 3. Arquitetura geral

```
┌─ planner_loop.py (determinístico) ────────────────────────────────┐
│                                                                    │
│  1. Trello watcher pega card                                       │
│  2. Cria Effort no vault, abre MOC                                 │
│  3. ▶ kickoff Crew Criativo (hierarchical)                        │
│       ┌─ Crew Criativo ────────────────────────────────────────┐  │
│       │  manager_llm                                           │  │
│       │  agentes: Researcher, Copywriter, Designer,            │  │
│       │           Image Artist, 3D Artist, Designer Reviewer   │  │
│       │                                                        │  │
│       │  Manager orquestra (fluxo natural):                    │  │
│       │   Researcher (10+ refs + Frankenstein) →               │  │
│       │   Copywriter → Designer (manifest) →                   │  │
│       │   Image Artist (generate_all_images) →                 │  │
│       │   3D Artist (generate_all_glbs) →                      │  │
│       │   Designer Reviewer → "bundle pronto"                  │  │
│       └────────────────────────────────────────────────────────┘  │
│  4. librarian.after_research / after_copy / after_design /         │
│     after_assets — operacional + judgment                          │
│  5. ▶ Dev (Claude CLI com sentinel + thread mgmt)                 │
│  6. librarian.after_dev — operacional + judgment                   │
│  7. ▶ kickoff Crew QA (hierarchical) — loop até N=2 retries       │
│       ┌─ Crew QA ──────────────────────────────────────────────┐  │
│       │  manager_llm                                           │  │
│       │  agentes: QA-código, QA-visual                         │  │
│       │                                                        │  │
│       │  QA-código (revisão text-based) →                      │  │
│       │   se reprova: Manager redige fix_prompt → return       │  │
│       │   se aprova: QA-visual sobe server, tira prints,       │  │
│       │              compara com refs do Researcher            │  │
│       │   se reprova: Manager agrega issues + redige fix       │  │
│       │   se aprova: bundle deploy-ready                       │  │
│       └────────────────────────────────────────────────────────┘  │
│  8. Se reprovado E attempt < 2: Dev re-roda com fix_prompt.md      │
│     Se attempt = 2 e ainda reprovado: status=qa_blocked, exit      │
│  9. librarian.after_qa_visual — operacional + judgment             │
│  10. DevOps deploy (GitHub + Netlify) — inalterado                 │
│  11. librarian.after_deploy — inalterado                           │
└────────────────────────────────────────────────────────────────────┘
```

## 4. Crew Criativo

### 4.1 Manager (manager_llm)

Configurado via `Crew(process=Process.hierarchical, manager_llm=llm)`. O CrewAI delega automaticamente. O prompt do Manager é gerado pelo CrewAI mas pode ser influenciado via:

- `Crew.manager_agent` (override completo) — opcional pra customizar role/goal/backstory
- Goal recomendado: "Diretor Criativo. Decide a sequência ideal de agentes para entregar bundle visual+textual+assets pronto, garantindo que o tom da copy bate com o estilo das referências e que cada asset reflete o Frankenstein proposto pelo Researcher."

### 4.2 Researcher (novo agente)

**Definição em `agents.py`:**
```python
def create_researcher() -> Agent:
    return Agent(
        role="Pesquisador de Referências e Concorrência",
        goal=(
            "Entregar dossiê com 10+ sites do segmento: 5 inspiracionais top "
            "(awwwards/dribbble/behance) + 5 concorrentes diretos. Para cada um, "
            "screenshots por seção (hero, mid, footer) e análise via vision LLM. "
            "Propor 'Frankenstein': qual hero usar de qual ref, qual seção 2, etc."
        ),
        backstory=(
            "Você é designer/UX research da Black Elephant. Conhece awwwards de cor. "
            "Filtra refs por segmento (SaaS, e-commerce, agência, fintech) e identifica "
            "padrões de mercado. Awwwards é a referência principal."
        ),
        tools=[WebSearchTool(), AwwwardsTool(), BrowserCaptureTool(), VisionAnalysisTool()],
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )
```

**4 tools novas:**

1. **`web_search_tool.py`** — busca DuckDuckGo (sem API key necessária, usa biblioteca `duckduckgo-search`). Input: query string. Output: lista de `{url, title, snippet}`. Usado pra encontrar sites de competidores ("plataforma de cursos online Brasil concorrentes").

2. **`awwwards_tool.py`** — scraping das páginas de categoria do awwwards (`/websites/{category}/`), dribbble (`/shots?tags=...`) e behance (`/search/projects/?search=...`). Filtra por SOTD/winners. Mesma interface, parsers diferentes por site.

3. **`browser_capture_tool.py`** (Playwright sync) — recebe URL, abre headless, espera `networkidle`, scrolla página inteira em passos de 80% da viewport, captura:
   - `full.png` — full-page screenshot
   - `hero.png` — above-the-fold (1920x1080)
   - `section_N.png` — uma por viewport até o footer
   - Salva em `output/{slug}/research/{ref_id}/`
   - Rate limit: 1 req/s via `playwright_helper.py` (lock global compartilhado)

4. **`vision_analysis_tool.py`** — usa o `vision_llm` que já existe (mesmo do Designer Reviewer). Input: path de screenshot + contexto ("seção hero de SaaS"). Output JSON estruturado: `{tipografia: "...", cores: ["..."], layout: "...", cta: "...", padroes: ["..."]}`.

**`playwright_helper.py`** — singleton com browser context compartilhado (não abre Chrome novo a cada call), stealth config (`playwright-stealth`), lock global pra rate limit. Reutilizado pelo `browser_capture_tool` E pelo `browser_qa_tool`.

**Output em `output/{slug}/research/references.json`:**
```json
{
  "segment": "saas-pricing-page",
  "inspirational": [
    {
      "ref_id": "ref_01",
      "source": "awwwards",
      "url": "https://example.com",
      "title": "Linear pricing",
      "screenshots": {
        "full": "output/slug/research/ref_01/full.png",
        "hero": "output/slug/research/ref_01/hero.png",
        "section_2": "output/slug/research/ref_01/section_2.png",
        "section_3": "output/slug/research/ref_01/section_3.png",
        "footer": "output/slug/research/ref_01/footer.png"
      },
      "analysis": {
        "hero": "Bold serif H1 96px, gradient bg purple/blue, single CTA",
        "section_2": "3-col grid, ícone+título+desc",
        "..."
      }
    }
  ],
  "competitors": [...],
  "frankenstein": {
    "hero":      {"from_ref": "ref_03", "why": "tipografia bold + CTA central com contraste forte"},
    "section_2": {"from_ref": "ref_07", "why": "grid de features 3-col com ícones lineart"},
    "pricing":   {"from_ref": "ref_01", "why": "toggle anual/mensal claro, destaque do plano popular"},
    "footer":    {"from_ref": "ref_05", "why": "footer minimal com newsletter inline"}
  },
  "market_patterns": {
    "ctas_comuns": ["Start free trial", "Book demo"],
    "pricing_styles": ["3-tier", "feature comparison table"],
    "prova_social": ["logos clients", "testemunhos com foto"]
  }
}
```

### 4.3 Copywriter, Designer, Image Artist, 3D Artist, Designer Reviewer

Esses agentes já existem em `agents.py`. Mudanças mínimas:

- **Copywriter:** task description ganha referência ao `references.json` ("Antes de escrever, leia o Frankenstein em `output/{slug}/research/references.json` e adote o tom dos exemplos do segmento.")
- **Designer:** mesma instrução. Vai usar `vision_analysis` das referências pra propor mood board no manifest.
- **Image Artist:** ganha tool agregada `generate_all_images(manifest_path)` — recebe path do manifest e itera (preserva o for-loop sequencial atual). Da perspectiva do Manager: 1 tool call.
- **3D Artist:** análogo, `generate_all_glbs(manifest_resolved_path)`.
- **Designer Reviewer:** inalterado.

### 4.4 Task de alto nível (`tasks.py`)

```python
def create_creative_brief_task(context: dict) -> Task:
    slug = context["slug"]
    return Task(
        description=(
            f"Você é o Diretor Criativo. Entregue bundle pronto pro Dev do projeto '{slug}'.\n\n"
            f"Briefing: {context['card_desc']}\n\n"
            f"Sequência sugerida (ajuste se necessário):\n"
            f"1. Researcher monta dossiê (5 refs awwwards/dribbble/behance + 5 competidores)\n"
            f"2. Copywriter escreve copy alinhado ao Frankenstein\n"
            f"3. Designer monta manifest visual usando refs\n"
            f"4. Image Artist gera todos PNGs (1 tool call: generate_all_images)\n"
            f"5. 3D Artist gera GLBs se necessário\n"
            f"6. Designer Reviewer aprova ou solicita regen\n\n"
            f"Reordene se algum passo ficar bloqueado. Conclua quando o manifest_resolved.json "
            f"estiver completo e o review do Designer aprovar."
        ),
        expected_output="JSON: {status: 'ready', manifest_resolved_path: '...', references_path: '...'}",
        agent=None,  # hierarchical — manager delega
    )
```

## 5. Crew QA

### 5.1 Manager (manager_llm)

Goal recomendado: "Lead QA. Garantir que o site entregue bate com referências, é tecnicamente sólido, e está pronto pra produção. Sempre roda QA-código primeiro; QA-visual só roda se QA-código aprovar. Se algum reprova, agrega issues + redige fix_prompt.md acionável pro Dev."

### 5.2 QA-código

Renomeado de `create_qa()` → `create_qa_code()`. Comportamento atual preservado. Lê arquivos do projeto, faz revisão textual, retorna `STATUS: APROVADO | REPROVADO` + lista de issues.

### 5.3 QA-visual (novo)

```python
def create_qa_visual() -> Agent:
    return Agent(
        role="QA Visual / UX Reviewer",
        goal=(
            "Comparar o site renderizado com referências do Researcher. "
            "Identificar problemas de espaçamento, alinhamento, tipografia, contraste, "
            "comportamento responsivo. Veredicto por seção. Se reprovado, redigir fix_prompt acionável."
        ),
        backstory=(
            "Designer-QA híbrido. Sabe ler um print e dizer 'essa margem está 8px maior, "
            "ref usa 96px'. Trabalha sempre com references.json em mãos."
        ),
        tools=[ServerRunnerTool(), BrowserQATool(), VisualDiffTool()],
        llm=vision_llm,
        verbose=False,
        allow_delegation=False,
    )
```

**3 tools novas:**

1. **`server_runner_tool.py`** — sobe o servidor do projeto:
   - Detecta `package.json` → checa script `dev`. Se faltar: `npm install` + `npm run dev`. Parseia porta via regex no stdout.
   - Senão: aloca porta livre via `socket`, roda `python -m http.server PORT --directory project_dir`.
   - Aguarda `GET /` → 200 (timeout 60s, polling 1s).
   - Retorna `{url, port, pid}`.
   - **Cleanup garantido em `finally`** — nunca deixa porta presa. Stub de teardown registrado no `atexit`.

2. **`browser_qa_tool.py`** (Playwright sync, reusa `playwright_helper.py`):
   - `screenshot_full(url) → path`
   - `screenshot_sections(url, count=N) → list[path]` — scrolla 80% viewport por vez
   - `screenshot_responsive(url) → {desktop_1920, desktop_1440, tablet_768, mobile_375}`
   - `inspect_element(url, selector) → path` — captura específica (botão, form)
   - Salva em `output/{slug}/qa_visual/current/`

3. **`visual_diff_tool.py`** — vision LLM compara `current/section_N.png` com `research/{ref_id}/section_N.png` (a do Frankenstein). Output:
   ```json
   [
     {
       "section": "hero",
       "verdict": "REPROVADO",
       "issues": [
         "Padding-top 40px abaixo da referência (ref usa 96px)",
         "CTA sem contraste — botão amarelo em fundo claro",
         "H1 está em 32px, ref usa 56px"
       ],
       "reference_used": "research/ref_03/hero.png",
       "current_screenshot": "qa_visual/current/hero.png"
     },
     {"section": "section_2", "verdict": "APROVADO", "issues": [], ...}
   ]
   ```

### 5.4 Output em `output/{slug}/qa_visual/`

```
current/
  desktop_1920.png
  desktop_1440.png
  tablet_768.png
  mobile_375.png
  hero.png
  section_2.png
  ...
report.json       # array de veredictos por seção
fix_prompt.md     # gerado pelo Manager do Crew QA se reprovado
```

**fix_prompt.md** (gerado pelo Manager agregando issues do QA-código + QA-visual):
```markdown
# Fix Prompt — Tentativa 2

## Issues de código (QA-código)
- LCP > 4s. Otimizar imports do Three.js (tree-shaking).
- Botão CTA sem `aria-label`.

## Issues visuais (QA-visual)

### Hero
- Aumentar padding-top de 40px → 96px
  - Comparar `qa_visual/current/hero.png` vs `research/ref_03/hero.png`
- Trocar fundo do CTA: `#fef9c3` → `#1e40af`, texto branco
- H1: 32px → 56px (font-size + line-height 1.1)

### Section 2 (features)
- Grid está 2-col, ref usa 3-col
  - Mudar `.features-grid` pra `grid-template-columns: repeat(3, 1fr)` em desktop

### Mobile (375px)
- Padding lateral 16px insuficiente, ref usa 24px
- Hero quebra: H1 ocupa 5 linhas, ref ocupa 3
  - Reduzir font-size mobile pra 32px
```

### 5.5 Loop de iteração no `planner_loop`

```python
MAX_QA_RETRIES = 2

for attempt in range(MAX_QA_RETRIES + 1):
    _set(9, "qa_crew", f"Crew QA revisando (tentativa {attempt+1}/{MAX_QA_RETRIES+1})...")
    qa_crew = Crew(
        agents=[qa_code, qa_visual],
        tasks=[create_qa_brief_task({
            "slug": slug,
            "project_dir": project_dir,
            "references_path": f"output/{slug}/research/references.json",
        })],
        process=Process.hierarchical,
        manager_llm=llm,
        verbose=False,
    )
    qa_result = qa_crew.kickoff()
    verdict = _parse_qa_verdict(qa_result)

    if verdict == "APROVADO":
        break

    if attempt < MAX_QA_RETRIES:
        fix_prompt = Path(f"output/{slug}/qa_visual/fix_prompt.md").read_text(encoding="utf-8")
        _set(8, "revision", f"Dev corrigindo (tentativa {attempt+2})...")
        dev_revision_run(slug, project_dir, fix_prompt)
    else:
        with _tasks_lock:
            task.status = "qa_blocked"
            task.log = f"Bloqueado pelo QA após {MAX_QA_RETRIES+1} tentativas"
        event_bus.emit("qa_blocked", f"❌ '{card_name}' bloqueado pelo QA")
        return
```

## 6. Bibliotecário com julgamento

### 6.1 Separação operacional vs conhecimento

| Tipo | O que é | Comportamento |
|---|---|---|
| **Operacional** | MOC do projeto, manifest do build, archive do effort, links de URL pós-deploy | Sempre escrito, sem julgamento. É accounting. |
| **Conhecimento** | Notas de aprendizado, dossiê de research, relatório QA-visual, listas de assets | Gated por `judge_artifact()` antes de indexar no Qdrant |

### 6.2 Função `judge_artifact()`

```python
def judge_artifact(artifact_type: str, content_summary: str, context: dict) -> dict:
    """
    Pergunta ao LLM julgador: vale indexar essa nota no Qdrant pra projetos futuros?
    
    artifact_type: "research" | "learnings" | "qa_visual" | "assets"
    content_summary: resumo curto do conteúdo (não o conteúdo completo)
    context: {slug, segment, stack, ...}
    
    Returns:
      {
        "save": bool,
        "ace_type": "atlas" | "resources",
        "tags": [str, ...],
        "priority": "high" | "medium" | "low",
        "reason": str,         # justificativa curta
        "summary": str,        # se save=True, resumo curado pra indexação
      }
    """
```

**Prompt do julgador (gemma local — rápido, barato, não bloqueia pipeline):**

```
Você é o bibliotecário do vault Ideaverse. Decida se esta nota deve ser
indexada no Qdrant pra busca semântica em projetos futuros.

Critérios SAVE (qualquer um):
- Padrão novo do segmento (ex: pricing inédito, animação rara)
- Stack inédita usada (ex: primeira vez com Astro, primeira fonte variable)
- Problema não-trivial resolvido (ex: bug de hydration esquisito)
- Insight de mercado específico (ex: "fintechs BR usam X de prova social")
- Referência visual rara/SOTW

Critérios SKIP (qualquer um):
- Padrão genérico já comum no vault (consulte o vault primeiro)
- Aprendizado óbvio (ex: "TS pega tipo errado")
- Dossiê fraco que não chegou a um Frankenstein claro
- Asset list genérico (sem id descritivo, sem propósito narrativo)

Antes de decidir: chame obsidian_vault_search com o tema dessa nota.
Se já houver 5+ notas similares, prefira SKIP a menos que essa traga ângulo novo.

Output JSON estrito:
{save: bool, ace_type, tags, priority, reason, summary}
```

### 6.3 Hooks atualizados

**`librarian.py` ganha duas funções novas + atualiza as existentes:**

```python
def after_research(slug: str, references_path: str, moc_path: str) -> None:
    refs = json.loads(Path(references_path).read_text(encoding="utf-8"))
    
    # OPERACIONAL: link no MOC sempre
    _link_in_moc(moc_path, "## Pesquisa", references_path)
    
    # CONHECIMENTO: julga antes
    summary = _summarize_research(refs)  # 200 chars: segmento + Frankenstein highlights
    decision = judge_artifact("research", summary, {"slug": slug, "segment": refs["segment"]})
    
    if decision["save"]:
        note_path = _write_research_note(slug, refs, decision)  # Atlas/Utilities/Researcher/{date}-{slug}-references.md
        index_single_file(VAULT_PATH / note_path)
        log_event(None, "librarian_kept", {
            "artifact": "research", "priority": decision["priority"], "reason": decision["reason"]
        })
    else:
        log_event(None, "librarian_skipped", {
            "artifact": "research", "reason": decision["reason"]
        })


def after_qa_visual(slug: str, report_path: str, screenshots_dir: str, moc_path: str) -> None:
    report = json.loads(Path(report_path).read_text(encoding="utf-8"))
    
    # OPERACIONAL: link no MOC sempre
    _link_in_moc(moc_path, "## QA Visual", report_path)
    
    # CONHECIMENTO: julga antes
    summary = _summarize_qa_visual(report)  # quantas reprovações, top 3 issues
    decision = judge_artifact("qa_visual", summary, {"slug": slug})
    
    if decision["save"]:
        note_path = _write_qa_visual_note(slug, report, screenshots_dir, decision)
        index_single_file(VAULT_PATH / note_path)
        log_event(None, "librarian_kept", {"artifact": "qa_visual", ...})
    else:
        log_event(None, "librarian_skipped", {"artifact": "qa_visual", "reason": decision["reason"]})
```

**`after_dev`, `after_assets`, `after_design` ganham mesmo padrão:** parte operacional (MOC) inalterada, parte conhecimento (Atlas/Notes) agora passa por `judge_artifact()`.

### 6.4 Override por confidence

Se `priority: high` E `save: True`:
- Tag `#high-value` adicionada
- Payload no Qdrant ganha `priority: 1.0` (booster em buscas)

Se `low`:
- Indexada com `priority: 0.5` (peso menor mas ainda buscável)

`obsidian_indexer.py` já suporta payload custom — só precisa propagar o campo `priority`.

### 6.5 Recuperação de skips

- `log_event("librarian_skipped", ...)` sempre emitido com razão
- O **arquivo bruto** (`output/{slug}/research/references.json`, etc.) sempre permanece em `output/` — só não vai pro vault. Pode ser reindexado manualmente depois se for descoberto que era valioso.
- Comando admin: `python -m server.librarian_force_index --slug X --artifact research` (escopo futuro, fora deste spec).

## 7. Arquivos novos e modificados

### Novos arquivos

```
server/
  web_search_tool.py              # DuckDuckGo search
  awwwards_tool.py                # Scraping awwwards/dribbble/behance
  browser_capture_tool.py         # Playwright screenshots por seção
  vision_analysis_tool.py         # vision_llm analisa prints (research)
  playwright_helper.py            # Singleton browser context + stealth + rate limit
  server_runner_tool.py           # Sobe servidor do projeto (npm dev / http.server)
  browser_qa_tool.py              # Playwright multi-viewport, scroll, inspect
  visual_diff_tool.py             # vision_llm compara current vs ref
```

### Modificados

```
server/
  agents.py            # +create_researcher, +create_qa_visual, rename create_qa→create_qa_code
  tasks.py             # +create_creative_brief_task, +create_qa_brief_task; ajusta copy/designer pra usar references.json
  flux_tool.py         # +tool agregada generate_all_images chamando o for-loop atual
  hunyuan3d_tool.py    # +tool agregada generate_all_glbs análoga
  librarian.py         # +after_research, +after_qa_visual, +judge_artifact, refactor após_dev/após_design/após_assets pra usar judgment
  planner_loop.py      # substitui steps 2-6 por kickoff Crew Criativo, substitui step 8 por loop Crew QA
  api.py               # +entradas no agents map (researcher, qa_visual)
  obsidian_indexer.py  # propaga campo priority do payload (se ainda não fizer)
```

## 8. Dependências externas

- **`playwright`** (Python) — `pip install playwright && playwright install chromium`
- **`playwright-stealth`** — `pip install playwright-stealth`
- **`duckduckgo-search`** — `pip install duckduckgo-search` (ou usar `httpx` direto contra HTML)

Tudo local, sem API keys novas. Forge e Hunyuan já estão rodando localmente.

## 9. Eventos pro frontend

CrewAI emite eventos por agent step (`step_callback`). Mapeamos no `planner_loop.py`:

| Agente em execução | step | status (pra frontend) |
|---|---|---|
| Researcher | 2 | `researching` |
| Copywriter | 3 | `copywriting` |
| Designer | 4 | `designing` |
| Image Artist | 5 | `imagining` |
| 3D Artist | 6 | `modeling_3d` |
| Designer Reviewer | 7 | `reviewing_assets` |
| Dev (Claude CLI) | 8 | `developing` |
| QA-código | 9 | `qa_code` |
| QA-visual | 10 | `qa_visual` |
| Dev (revisão) | 9 | `revision` |
| DevOps | 11 | `deploying` |

Frontend (`api.py:178+` agents map) ganha 2 entradas novas: `researcher` e `qa_visual`.

## 10. Testing strategy

| Camada | Estratégia |
|---|---|
| Tools individuais | Unit tests com fixtures: `awwwards_tool` mocked HTML; `browser_capture_tool` com página HTML local; `visual_diff_tool` com pares de imagens conhecidas |
| `playwright_helper` | Test que verifica singleton, rate limit ≥ 1s entre calls, stealth ativo |
| `server_runner_tool` | Test sobe `python -m http.server` em diretório fixture, valida cleanup mesmo em exception |
| `judge_artifact` | Test com prompts/respostas mockadas: garante parsing JSON estrito, fallback se LLM retorna malformed |
| Crew Criativo | Integration test com manifest fixture, verifica que `references.json` é gerado e que `manifest_resolved.json` aparece no fim |
| Crew QA | Integration test com projeto fixture (HTML+CSS conhecidamente "errado") + `references.json` mock → verifica que reprova e `fix_prompt.md` aparece |
| Loop de iteração | Test que simula reprova-aprovação no attempt 2, e reprova-reprova-reprova → `qa_blocked` |
| Bibliotecário | Test que `after_research` com mock de `judge_artifact` retornando `save=False` NÃO indexa no Qdrant mas atualiza MOC |

## 11. Riscos e mitigações

| Risco | Mitigação |
|---|---|
| Awwwards bloqueia scraping | playwright-stealth + user-agent real + rate limit 1s. Se bloqueio persistir, fallback pra cache de URLs do awwwards SOTW (RSS público). |
| Servidor do projeto Dev não sobe (porta presa, deps faltando) | `server_runner_tool` aloca porta livre via `socket.bind(0)`. Cleanup em `finally` + `atexit`. Se `npm install` falha 2x, marca QA como `qa_visual_unavailable` mas não bloqueia deploy. |
| Vision LLM dá veredicto inconsistente | Usar mesmo `vision_llm` do Designer Reviewer (já validado). Prompt do `visual_diff_tool` é estrito: JSON only, sem hedge. |
| Manager LLM entra em loop (re-roda Researcher 5x) | CrewAI tem `max_iter` por agente. Setar `max_iter=3` no Researcher. Manager LLM tem seu próprio limite via `max_rpm` da Crew. |
| Bibliotecário julga errado e descarta info importante | Sempre logar `librarian_skipped` com razão. Arquivo bruto em `output/` permanece. Comando manual de re-index futuro. |
| Tools agregadas (`generate_all_images`) escondem progresso por imagem | Tool emite `event_bus.emit("image_progress", {current, total})` a cada iteração — frontend mostra contagem. |

## 12. Sucesso

- Pipeline completa um card do Trello sem intervenção, do briefing ao deploy, com o Manager decidindo a sequência (não código hardcoded em `planner_loop`)
- Site final passa por QA visual e reflete pelo menos 3 das 4 áreas do Frankenstein (hero, seção 2, pricing, footer)
- Loop de iteração funciona: ao reprovar, Dev recebe `fix_prompt.md` e re-roda; QA visual aprova na segunda tentativa em ≥ 70% dos casos de teste
- Bibliotecário descarta ≥ 30% dos artifacts em projetos repetitivos (mesmo segmento já trabalhado), e mantém ≥ 90% em projetos com stack/segmento novo
- Vault Qdrant não cresce linearmente com cada projeto — apenas conhecimento útil é indexado
