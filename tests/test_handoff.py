def test_generate_handoff_returns_llm_output(monkeypatch):
    from server import handoff
    monkeypatch.setattr(handoff, "_call_llm",
                        lambda prompt: "Pesquisa pronta, 5 refs, passando pro Copy.")

    handoff._generate_cached.cache_clear()
    out = handoff.generate_handoff("researcher", "Researcher", "5 refs do Frankenstein", "Copywriter")
    assert "passando pro Copy" in out


def test_generate_handoff_truncates_to_140(monkeypatch):
    from server import handoff
    monkeypatch.setattr(handoff, "_call_llm", lambda p: "x" * 500)
    handoff._generate_cached.cache_clear()
    out = handoff.generate_handoff("a", "A", "y", "B")
    assert len(out) <= 140


def test_generate_handoff_falls_back_on_exception(monkeypatch):
    from server import handoff
    def boom(p):
        raise RuntimeError("llm offline")
    monkeypatch.setattr(handoff, "_call_llm", boom)
    handoff._generate_cached.cache_clear()
    out = handoff.generate_handoff("dev", "Dev", "build ok", "QA")
    assert "Dev" in out
    assert "QA" in out


def test_generate_handoff_caches(monkeypatch):
    from server import handoff
    calls = []
    monkeypatch.setattr(handoff, "_call_llm",
                        lambda p: calls.append(p) or "ok")
    handoff._generate_cached.cache_clear()

    handoff.generate_handoff("a", "A", "did x", "B")
    handoff.generate_handoff("a", "A", "did x", "B")
    assert len(calls) == 1


def test_generate_handoff_handles_no_next_agent(monkeypatch):
    from server import handoff
    monkeypatch.setattr(handoff, "_call_llm",
                        lambda p: "Pipeline concluido.")
    handoff._generate_cached.cache_clear()
    out = handoff.generate_handoff("devops", "DevOps", "deploy ok", None)
    assert "concluido" in out.lower() or "DevOps" in out
