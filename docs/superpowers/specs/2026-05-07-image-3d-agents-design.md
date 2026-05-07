# Agentes Imagens + 3D no Pipeline (com Designer revisor)

**Data:** 2026-05-07
**Status:** Design aprovado, pendente plano de implementação

## Problema

O pipeline atual de 7 etapas (`server/planner_loop.py`) entrega sites Three.js/GSAP, mas o Dev precisa improvisar imagens (placeholders, Unsplash) e modelos 3D (geometrias primitivas). Falta um par de agentes especialistas que produzam assets visuais coerentes com o guia do Designer antes do Dev começar.

## Objetivo

1. Adicionar dois agentes ao pipeline existente:
   - **Image Artist** — gera PNGs via Flux Schnell NF4 (Stable Diffusion WebUI Forge em `127.0.0.1:7860`).
   - **3D Artist** — gera GLBs via Hunyuan3D-2GP (servidor em `127.0.0.1:8081`) a partir de PNGs gerados pelo Image Artist.
2. O Designer existente passa a produzir um **asset manifest** estruturado e a **revisar** as imagens via vision LLM.
3. Os dois agentes ficam **visíveis no game** como NPCs com indicador de status e whisper bubble.
4. O Bibliotecario organiza os assets no Obsidian.
5. Ajustar consumo de Qdrant para a nova porta/API key.

## Não-objetivos

- Renderização headless de GLB para revisão visual (deixado como extensão futura).
- Endpoint HTTP novo em `server/api.py` para chamar Image/3D individualmente fora do pipeline.
- `img2img`, ControlNet, ou refinamento iterativo de imagens.
- Cache de imagens/modelos por prompt.
- Substituir o LLM principal — vision LLM convive com `deepseek/deepseek-v4-flash` apenas no agente revisor.

## Pipeline Final (10 etapas)

```
1. Planner       (MOC + Effort no vault)
2. Copywriter    (copy markdown → vault)
3. Designer      (guia visual + asset_manifest JSON → vault)
4. Image Artist  (gera PNGs do manifest → output/{slug}/assets/)
5. Designer Rev  (vision LLM revisa cada PNG; max 1 retry de regen)
6. 3D Artist     (gera GLBs dos PNGs com convert_to_3d=true)
7. Developer     (consome guia + manifest_resolved → Claude CLI)
8. QA            (revisão estática; loop de revisão se REPROVADO)
9. DevOps        (push GitHub + deploy Netlify)
10. Planner      (fechamento + Trello → DONE)
```

Todas as etapas respeitam o cancelamento da task (check `task.status == "cancelled"` antes de cada etapa).

## Asset Manifest (contrato Designer→Imagens→3D)

O Designer continua devolvendo o guia em markdown, mas anexa no final um bloco JSON delimitado por fence:

````
```asset_manifest
{
  "images": [
    {
      "id": "hero",
      "prompt_pt": "fundo abstrato escuro com partículas douradas",
      "purpose": "background da seção hero",
      "width": 1920,
      "height": 1080,
      "convert_to_3d": false
    },
    {
      "id": "logo_mascote",
      "prompt_pt": "mascote elefante 3D estilizado, fundo branco, vista frontal",
      "purpose": "logo animado em three.js",
      "width": 1024,
      "height": 1024,
      "convert_to_3d": true
    }
  ]
}
```
````

**Por que JSON em fence:** Image Artist itera item-por-item; markdown forçaria mais um round de LLM pra extrair. Fence delimitado é parseável com regex + `json.loads` sem ambiguidade.

**Resolução incremental** — após Imagens roda:

```json
{
  "images": [
    {"id": "hero", "png_path": "output/cafe-central/assets/hero.png", "purpose": "..."},
    {"id": "logo_mascote", "png_path": "...", "purpose": "...", "convert_to_3d": true}
  ]
}
```

Após 3D roda:

```json
{
  "images": [
    {"id": "hero", "png_path": "...", "purpose": "..."},
    {"id": "logo_mascote", "png_path": "...", "glb_path": "output/cafe-central/assets/logo_mascote.glb", "purpose": "..."}
  ]
}
```

Salvo em `output/{slug}/assets/manifest_resolved.json`. Dev consome no prompt do Claude CLI.

## Arquivos

### Novos

| Arquivo | Função |
|---|---|
| `server/flux_tool.py` | `FluxImageTool(BaseTool)` — POST `127.0.0.1:7860/sdapi/v1/txt2img`, salva PNG em `output_dir`, retorna path absoluto. Configuração via `FORGE_API_URL`. Defaults: `steps=4`, `cfg_scale=1`, `sampler="Euler"`, `width=1024`, `height=1024`. Timeout 600s. Implementação ipsis litteris da seção 4.1 de `crewai-flux-agent.md`. |
| `server/hunyuan3d_tool.py` | `Hunyuan3DTool(BaseTool)` — POST `127.0.0.1:8081/generate`, recebe `image_path`, retorna path do GLB. Configuração via `HUNYUAN_API_URL`. Defaults: `octree_resolution=128`, `num_inference_steps=5`, `guidance_scale=5.0`, `seed=1234`. Timeout 600s. Adaptado de `C:\AI\Hunyuan3D-2GP\crewai_integration\hunyuan3d_tool.py`. Valida que `image_path` existe antes do POST. |
| `server/asset_manifest.py` | `parse_manifest(designer_output: str) -> dict` (extrai bloco `asset_manifest` por regex e parseia JSON; falhas retornam `{"images": []}` + log warning). `write_resolved(slug: str, manifest: dict) -> Path`. `read_resolved(slug: str) -> dict`. |
| `tests/test_flux_tool.py` | Conforme seção 5 de `crewai-flux-agent.md`: `test_flux_tool_saves_png`, `test_flux_tool_handles_api_error`. |
| `tests/test_hunyuan3d_tool.py` | `test_hunyuan_returns_glb_path` (mock POST → JSON com `path`), `test_hunyuan_handles_api_error` (ConnectionError), `test_hunyuan_validates_image_exists` (path inexistente → erro antes do POST). |
| `tests/test_asset_manifest.py` | `test_parse_valid_manifest`, `test_parse_missing_fence`, `test_parse_invalid_json`, `test_parse_extracts_only_first_fence`. |
| `tests/test_pipeline_assets.py` | Stub de `Crew.kickoff` para retornar manifest fake; valida (a) `manifest_resolved.json` é escrito com `png_path` e `glb_path`; (b) step count chega em 10; (c) Hunyuan offline em todas as imagens NÃO aborta; (d) Forge offline em todas aborta com `task.status == "error"`; (e) Designer review reprovado dispara 1 regen e segue. |

### Modificados

| Arquivo | Mudança |
|---|---|
| `server/agents.py` | + `vision_llm` (LLM separada apontando pra `openai/gpt-4o-mini` via OpenRouter, modelo override por env `VISION_MODEL`). + `create_image_artist()` (tools: `[FluxImageTool()]`, `llm=llm`). + `create_3d_artist()` (tools: `[Hunyuan3DTool()]`, `llm=llm`). + `create_designer_reviewer()` (mesma persona do designer mas `llm=vision_llm`, tools vazias). |
| `server/tasks.py` | + `create_image_pipeline_task(agent, context)` (recebe `slug`, `manifest`, itera images, chama `flux_image` por item, escreve `manifest_resolved.json`). + `create_3d_pipeline_task(agent, context)` (lê `manifest_resolved.json`, filtra `convert_to_3d=true`, chama `hunyuan3d` por item, atualiza `manifest_resolved.json` com `glb_path`). + `create_designer_review_task(agent, context)` (recebe `manifest_resolved`, monta mensagem multimodal com cada PNG em base64 + `purpose` + trecho do guia, espera JSON: `{"reviews": [{"id", "verdict", "reason", "regen_prompt"}]}`). **Modifica `create_designer_task()`** acrescentando exigência do bloco `asset_manifest` JSON no final. |
| `server/planner_loop.py` | Pipeline cresce de 7 para 10 etapas. Status enum ganha `imagining`, `reviewing_assets`, `regen_assets`, `modeling_3d`. Adiciona helpers `_run_imagining()`, `_run_designer_review()` (com loop de regen, max_retries=1), `_run_3d()`. `step` field e prints sobem de `[N/7]` pra `[N/10]`. Atualiza chamada `librarian.after_*` em pontos novos. |
| `server/api.py` | + 2 entradas em `AGENT_SEED`: `image_artist` em col=1, row=4, sprite_char=4. `agente_3d` em col=3, row=4, sprite_char=5. Atualiza `_AGENT_DISPLAY` com os display names. Adiciona `api_key=os.getenv("QDRANT_API_KEY")` ao `QdrantClient` na linha 419. |
| `server/obsidian_indexer.py` | + `QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")` no topo. Adiciona `api_key=QDRANT_API_KEY` aos 3 `QdrantClient(...)`. |
| `server/vault_tool.py` | Mesma mudança: lê env e passa `api_key` ao `QdrantClient`. |
| `server/librarian.py` | + `after_design(slug, guide_path, manifest_json_str, moc_path, index=True)` — escreve `Atlas/Utilities/Designer/{date}-{slug}-manifest.json` no vault e atualiza MOC com seção `## Design`. + `after_assets(slug, resolved_manifest, project_dir, moc_path, index=True)` — escreve `Atlas/Utilities/ImageArtist/{date}-{slug}-assets.md` (tabela com id/prompt/path) e `Atlas/Utilities/3DArtist/{date}-{slug}-models.md` (tabela com id/glb_path/source_image), atualiza MOC com `## Imagens` e `## Modelos 3D`. |
| `src/ui/TasksPanel.ts` | + 4 entradas em `STATUS_TO_AGENT` (linha 45): `imagining→image_artist`, `reviewing_assets→designer`, `regen_assets→image_artist`, `modeling_3d→agente_3d`. + 2 entradas em `AGENT_INFO` (linha 56): `image_artist`, `agente_3d` (initials, color, role). + 4 entradas em `ACTIVE_STATUSES` (linha 65). |
| `.env.example` (se existir) ou doc | Adiciona `QDRANT_API_KEY=` (vazio com comentário), `VISION_MODEL=openai/gpt-4o-mini`, `FORGE_API_URL=http://127.0.0.1:7860`, `HUNYUAN_API_URL=http://127.0.0.1:8081`. |

### Não modificados

- `requirements.txt` — `requests` é transitivo via crewai. Não há lib nova.
- `agents.py`, `tasks.py`, `trello_tool.py` na raiz — legado, conforme nota em `crewai-flux-agent.md` seção 3.
- `src/game/NPC.ts`, `src/main.ts` — visualização dos NPCs novos é data-driven via `/api/agents`. Indicador de status e whisper bubble já funcionam para qualquer NPC registrado.

## Visualização no Game

Os 2 NPCs novos aparecem automaticamente assim que o seed roda:

- `image_artist`: posição `(col=1, row=4)`, sprite `front_4_iddle.png`, à esquerda do Designer.
- `agente_3d`: posição `(col=3, row=4)`, sprite `front_5_iddle.png`, à direita do Designer.

Comportamento existente que se aplica sem código novo:
- Indicador amarelo (idle) → verde (working) gerenciado pelo `tasksPanel.setAgentWorkingCallback` em `src/main.ts:51`, que recebe o conjunto de NPC IDs ativos derivado do `STATUS_TO_AGENT` em `src/ui/TasksPanel.ts:45`.
- Whisper bubble com tokens do LLM em streaming via `_tls.task_id` em `planner_loop.py:259` e `connectEventStream` em `src/ui/AgentToast.ts`. O matching atual ("primeiro NPC com `isWorking=true`" em `src/main.ts:60`) funciona porque o pipeline é estritamente sequencial.

**Pré-requisito** — pra os indicadores acenderem nos NPCs corretos, são necessárias mudanças em **2 lugares**:

1. **Backend** (`server/planner_loop.py`): adicionar status novos no enum (`imagining`, `reviewing_assets`, `regen_assets`, `modeling_3d`) e setá-los antes de cada kickoff via o helper `_set(step, status, log)` já existente.

2. **Frontend** (`src/ui/TasksPanel.ts`):
   - Estender `STATUS_TO_AGENT` (linha 45) com:
     ```ts
     imagining:        "image_artist",
     reviewing_assets: "designer",
     regen_assets:     "image_artist",
     modeling_3d:      "agente_3d",
     ```
   - Estender `AGENT_INFO` (linha 56) com entradas para `image_artist` e `agente_3d` (initials, color, role).
   - Estender `ACTIVE_STATUSES` (constante usada em `updateBadge`) com os 4 status novos.

## Designer Review (etapa 5 detalhada)

**Input:** `manifest_resolved.json` com `png_path` por imagem; trecho do guia visual; ID/purpose por imagem.

**Como o LLM "vê" cada imagem:** `create_designer_review_task` lê cada PNG, base64-encoda, monta mensagem multimodal (formato OpenRouter/OpenAI: `{"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}` ao lado do texto). O `vision_llm` (gpt-4o-mini) recebe a mensagem e responde JSON estruturado.

**Output esperado do LLM:**
```json
{
  "reviews": [
    {"id": "hero", "verdict": "APROVADO", "reason": "Atende ao mood escuro/dourado pedido"},
    {"id": "logo_mascote", "verdict": "REPROVADO", "reason": "Sem fundo branco, postura ambígua", "regen_prompt": "elefante mascote estilizado, fundo BRANCO PURO, vista frontal centralizada, estilo flat 3D, alta resolução"}
  ]
}
```

**Loop de regen:**
- Para cada `REPROVADO`, Image Artist regenera com `regen_prompt` (chamada `flux_image` direta, não nova rodada do agente — mais rápido e determinístico).
- Após regen, segunda passagem do Designer Review.
- Se ainda `REPROVADO` na segunda passagem: log warning, segue para etapa 6 com a imagem que tiver. **Não bloqueia o pipeline.**

**Edge cases:**
- LLM devolve JSON malformado → tratamos como `APROVADO` em todos (warning no log; bloquear pipeline por failure de parsing seria pior UX).
- Manifest vazio (sem imagens) → etapa 5 vira no-op em 1 segundo.

## Error Handling

| Situação | Comportamento |
|---|---|
| Designer não devolve bloco `asset_manifest` | Warning no log, manifest = `{"images": []}`, etapas 4/5/6 viram no-ops, pipeline segue para Dev. |
| Forge offline na etapa 4 | Loga erro por imagem, pula a falhada. Se **todas** falharem → `task.status = "error"`, aborta. |
| Hunyuan offline na etapa 6 | Mesmo padrão de Forge, mas **não aborta** mesmo se todas falharem. Dev funciona com PNGs. |
| Imagem com `convert_to_3d=true` mas PNG dela falhou | 3D pula silenciosamente esse item. |
| Vision LLM offline na etapa 5 | Loga erro, pipeline trata como tudo aprovado, segue. |
| Cancelamento durante 4/5/6 | Check `task.status == "cancelled"` antes de cada item iterado e antes de cada etapa. |

**Justificativa da assimetria Image vs 3D:** site sem imagens fica visualmente quebrado; site sem GLB ainda renderiza (decoração).

## Bibliotecario (Obsidian)

Estrutura no vault após pipeline:

```
Atlas/
├── Maps/
│   └── {slug} MOC.md                            (atualizado com seções novas)
├── Utilities/
│   ├── Designer/
│   │   ├── {date}-{slug}-visual-guide.md        (já existia)
│   │   └── {date}-{slug}-manifest.json          (NOVO)
│   ├── ImageArtist/
│   │   └── {date}-{slug}-assets.md              (NOVO — tabela id/prompt/path)
│   └── 3DArtist/
│       └── {date}-{slug}-models.md              (NOVO — tabela id/glb_path/source)
└── Notes/
    └── Sources/Copywriter/{date}-{slug}-copy.md (já existia)
```

MOC do projeto ganha seções:
```markdown
## Design
- [[{date}-{slug}-visual-guide]]
- Manifest: [[{date}-{slug}-manifest|asset_manifest.json]]

## Imagens
- [[{date}-{slug}-assets|Lista de PNGs gerados]]

## Modelos 3D
- [[{date}-{slug}-models|Lista de GLBs gerados]]
```

Chamadas no `_run_pipeline`:
- `librarian.after_design(slug, guide_path, manifest_str, moc_path)` — após etapa 3.
- `librarian.after_assets(slug, resolved_manifest, project_dir, moc_path)` — após etapa 6.

## Qdrant — Migração para 6333 com API Key

Lugares afetados:
- `server/obsidian_indexer.py` — 3 instâncias de `QdrantClient`.
- `server/vault_tool.py` — 1 instância na linha 44.
- `server/api.py` — 1 instância na linha 419.

Padrão novo:
```python
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
client = QdrantClient(
    url=QDRANT_URL,
    api_key=QDRANT_API_KEY,
    check_compatibility=False,
)
```

A chave (`q5QloVfwwtlnb1RbL3li3Bfkk/5ImAngraXkOAU3jwQ=`) vai no `.env` local. **Não commitar.** Confirmar que `.env` está no `.gitignore`.

## Vision LLM

Adicionar em `server/agents.py` ao lado do `llm` existente:
```python
vision_llm = LLM(
    model=os.environ.get("VISION_MODEL", "openai/gpt-4o-mini"),
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ.get("OPENROUTER_API_KEY", ""),
    stream=True,
)
```

Apenas o `create_designer_reviewer()` usa `vision_llm`. Demais agentes seguem com `llm` original (deepseek). Razão: vision tem custo maior por token; só usar onde precisa de fato ver imagens.

## Testes

**Unitários (mock HTTP, sem rede real):**
- `tests/test_flux_tool.py` — 2 cases (save PNG; erro de conexão).
- `tests/test_hunyuan3d_tool.py` — 3 cases (retorna GLB; erro; valida image existe).
- `tests/test_asset_manifest.py` — 4 cases (válido; sem fence; JSON inválido; múltiplos fences).
- `tests/test_pipeline_assets.py` — 5 cases listados acima na tabela de arquivos.

**Verificação manual** (executor DEVE rodar antes de declarar pronto):
1. Subir Forge: `stable-diffusion-webui-forge\webui-user.bat` (com `--api`). Testar `curl http://127.0.0.1:7860/sdapi/v1/sd-models`.
2. Subir Hunyuan: `cd C:\AI\Hunyuan3D-2GP; .\run_server.ps1`. Aguardar `Uvicorn running on http://127.0.0.1:8081`.
3. Subir backend BE-Game: `python -m uvicorn server.api:app --port 8000`.
4. Abrir o game no browser, confirmar que os 2 NPCs novos aparecem (`image_artist`, `agente_3d`) ao redor do Designer.
5. Criar card no Trello com briefing simples (ex: "Site para cafeteria boutique").
6. Acompanhar pelo game: indicadores ficam verdes em sequência (Imagens → Designer Rev → 3D), com whisper streaming.
7. Verificar `output/{slug}/assets/`: pelo menos 1 PNG > 100KB, ao menos 1 GLB se algum item tinha `convert_to_3d=true`.
8. Verificar `manifest_resolved.json`: tem `png_path` em todos, `glb_path` nos com `convert_to_3d=true`.
9. Abrir o vault: `Atlas/Utilities/ImageArtist/{date}-{slug}-assets.md` e `3DArtist/{date}-{slug}-models.md` existem; MOC do projeto referencia ambos.
10. Abrir `index.html` gerado pelo Dev e confirmar que ele usa os PNGs/GLBs gerados (busca por `output/{slug}/assets/` ou paths copiados).

**Não testado (fora do escopo):**
- Qualidade visual subjetiva dos PNGs/GLBs.
- Performance (Hunyuan ~30s/modelo, é lento por design).
- Renderização headless de GLB para revisão visual.

## Restrições / o que NÃO fazer

- ❌ Não criar endpoint HTTP novo em `server/api.py` para Image/3D individuais. Acesso via pipeline apenas.
- ❌ Não adicionar `diffusers`, `torch`, ou outras libs pesadas. Integração é HTTP.
- ❌ Não retornar base64 das tools — sempre salvar em disco e retornar path.
- ❌ Não escrever inglês em `description`/`goal`/`backstory` dos agentes — manter PT-BR sem acentos especiais.
- ❌ Não modificar `stable-diffusion-webui-forge/` exceto, se necessário, `webui-user.bat` para garantir `--api`.
- ❌ Não tocar `agents.py`, `tasks.py`, `trello_tool.py` na raiz (legado).
- ❌ Não commitar `.env` com a API key do Qdrant.

## Extensão futura (fora do escopo)

- Renderização headless de GLB → PNG via puppeteer ou Blender, para Designer revisar modelos 3D também.
- `img2img` para refinamento iterativo de PNGs.
- Cache de imagens/modelos por hash de prompt.
- Endpoint HTTP individual para Image/3D, permitindo chat direto com cada agente.
- Paralelização de Image Artist (gerar múltiplos PNGs em concorrência se Forge suportar).
- ControlNet para guiar composição com base no layout do Designer.
