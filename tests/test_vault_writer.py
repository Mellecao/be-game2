# tests/test_vault_writer.py
import pytest
from pathlib import Path


def test_make_slug_basic():
    from server.vault_writer import make_slug
    assert make_slug("Rose Beauty Site") == "rose-beauty-site"


def test_make_slug_special_chars():
    from server.vault_writer import make_slug
    assert make_slug("Café & Pão") == "cafe-pao"


def test_make_slug_already_kebab():
    from server.vault_writer import make_slug
    assert make_slug("be-game") == "be-game"


def test_write_note_creates_file(tmp_path, monkeypatch):
    import server.vault_writer as vw
    monkeypatch.setattr(vw, "VAULT_PATH", tmp_path)

    result = vw.write_note(
        relative_path="Atlas/Notes/test.md",
        title="Título Teste",
        content="Conteúdo do teste.",
        agent_id="copywriter",
        ace_type="atlas",
        tags=["teste"],
        index=False,
    )

    assert result.exists()
    text = result.read_text(encoding="utf-8")
    assert "agent: copywriter" in text
    assert "# Título Teste" in text
    assert "Conteúdo do teste." in text


def test_write_note_creates_parent_dirs(tmp_path, monkeypatch):
    import server.vault_writer as vw
    monkeypatch.setattr(vw, "VAULT_PATH", tmp_path)

    vw.write_note(
        relative_path="Atlas/Notes/Agentes/Copywriter/nova-nota.md",
        title="Nova",
        content="corpo",
        agent_id="copywriter",
        ace_type="atlas",
        index=False,
    )

    assert (tmp_path / "Atlas/Notes/Agentes/Copywriter/nova-nota.md").exists()


def test_write_note_no_clobber(tmp_path, monkeypatch):
    import server.vault_writer as vw
    monkeypatch.setattr(vw, "VAULT_PATH", tmp_path)

    p1 = vw.write_note(relative_path="dir/a.md", title="A", content="1", agent_id="qa", ace_type="cards", index=False)
    p2 = vw.write_note(relative_path="dir/a.md", title="A", content="2", agent_id="qa", ace_type="cards", index=False)

    assert p1 != p2   # second write got a timestamped suffix
    assert p1.exists() and p2.exists()
