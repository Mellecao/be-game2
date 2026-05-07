# be-game

## Smoke test manual: pipeline com Manager + Researcher + QA visual

Pré-requisitos: Forge rodando (`http://127.0.0.1:7860`), Hunyuan3D rodando (`http://127.0.0.1:8081`), Ollama com Gemma local.

1. Subir o api server: `python -m uvicorn server.api:app --reload --port 8000`
2. Criar um card no Trello na lista monitorada com nome "smoke saas pricing" e descrição curta.
3. Aguardar o pipeline detectar (~5s poll) e iniciar.
4. Acompanhar logs:
   - `output/{slug}/research/references.json` deve aparecer com 5+ insp + 5+ comp
   - `output/{slug}/research/{ref_id}/full.png` etc devem existir
   - `output/{slug}/assets/manifest_resolved.json` ao fim do Crew Criativo
   - `output/{slug}/qa_visual/current/desktop_1920.png` etc após Dev
   - `output/{slug}/qa_visual/report.json` com veredictos
5. Conferir vault:
   - `Atlas/Maps/{slug} MOC.md` — seções `## Pesquisa`, `## QA Visual` preenchidas
   - `Atlas/Utilities/Researcher/...` — nota apenas se judgment aprovou
   - `Atlas/Utilities/QA-Visual/...` — idem
6. Conferir Qdrant:
   - Buscar `obsidian_vault_search "padrão hero saas"` deve retornar refs do projeto se foram indexadas.
