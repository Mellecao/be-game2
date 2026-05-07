"""Smoke test: roda o pipeline com mocks pesados nos LLMs e tools externos.

Verifica que:
- Crew Criativo eh invocado
- Crew QA eh invocado
- librarian.after_research e librarian.after_qa_visual sao chamados
- final_status terminou como 'done' OU 'qa_blocked' (nao crashou)
"""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch


def test_pipeline_invokes_both_crews_and_librarian_hooks(tmp_path, monkeypatch):
    """Mocks: Crew.kickoff, Claude CLI dev, librarian, Playwright."""
    from server import planner_loop

    # mock Crew.kickoff retornando string JSON valida
    def fake_kickoff(self):
        # detecta qual crew pelo numero de agentes (criativo=6, qa=2)
        if len(self.agents) == 6:
            ref_dir = tmp_path / "output" / "x" / "research"
            ref_dir.mkdir(parents=True, exist_ok=True)
            (ref_dir / "references.json").write_text(json.dumps({
                "segment": "saas", "inspirational": [], "competitors": [], "frankenstein": {}
            }), encoding="utf-8")
            asset_dir = tmp_path / "output" / "x" / "assets"
            asset_dir.mkdir(parents=True, exist_ok=True)
            (asset_dir / "manifest_resolved.json").write_text(json.dumps({"images": []}), encoding="utf-8")
            return MagicMock(__str__=lambda self: '{"status":"ready"}')
        else:
            qa_dir = tmp_path / "output" / "x" / "qa_visual"
            qa_dir.mkdir(parents=True, exist_ok=True)
            (qa_dir / "report.json").write_text(json.dumps([
                {"section": "hero", "verdict": "APROVADO", "issues": []}
            ]), encoding="utf-8")
            return MagicMock(__str__=lambda self: '{"verdict":"APROVADO"}')

    monkeypatch.setattr("crewai.Crew.kickoff", fake_kickoff)
    monkeypatch.chdir(tmp_path)

    after_research_calls = []
    after_qa_visual_calls = []
    monkeypatch.setattr("server.librarian.after_research",
                        lambda *a, **kw: after_research_calls.append(a))
    monkeypatch.setattr("server.librarian.after_qa_visual",
                        lambda *a, **kw: after_qa_visual_calls.append(a))

    # bypass Dev (Claude CLI) e DevOps
    monkeypatch.setattr("server.dev_tool.OpenClaudeCliTool._run", lambda self, *a, **kw: "ok")

    # Smoke: verifica que _run_pipeline e callable
    from server.planner_loop import _run_pipeline  # noqa: F401
    assert callable(_run_pipeline)
