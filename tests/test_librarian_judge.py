def test_judge_artifact_returns_save_true_for_novel(monkeypatch):
    from server import librarian

    fake_response = (
        '{"save": true, "ace_type": "atlas", "tags": ["fintech", "saas"], '
        '"priority": "high", "reason": "padrao novo de pricing", '
        '"summary": "fintech BR usa toggle anual com desconto destacado"}'
    )
    monkeypatch.setattr(librarian, "_judge_call", lambda prompt: fake_response)

    out = librarian.judge_artifact("research", "summary aqui", {"slug": "x", "segment": "fintech"})
    assert out["save"] is True
    assert out["priority"] == "high"
    assert "fintech" in out["tags"]


def test_judge_artifact_returns_save_false_for_redundant(monkeypatch):
    from server import librarian
    fake_response = (
        '{"save": false, "ace_type": "atlas", "tags": [], '
        '"priority": "low", "reason": "redundante com 8 notas existentes", '
        '"summary": ""}'
    )
    monkeypatch.setattr(librarian, "_judge_call", lambda prompt: fake_response)

    out = librarian.judge_artifact("research", "summary", {})
    assert out["save"] is False
    assert "redundante" in out["reason"]


def test_judge_artifact_falls_back_safe_on_malformed(monkeypatch):
    """Se LLM retornar JSON malformado, default = save=True (nao perder info)."""
    from server import librarian
    monkeypatch.setattr(librarian, "_judge_call", lambda prompt: "not json")

    out = librarian.judge_artifact("research", "summary", {})
    assert out["save"] is True
    assert out["priority"] == "medium"
    assert out["reason"].startswith("fallback")
