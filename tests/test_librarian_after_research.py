import json


def test_after_research_writes_moc_link_always(tmp_path, monkeypatch):
    import server.librarian as lib
    monkeypatch.setattr(lib, "VAULT_PATH", tmp_path)

    moc_dir = tmp_path / "Atlas" / "Maps"
    moc_dir.mkdir(parents=True)
    moc = moc_dir / "x MOC.md"
    moc.write_text("## Pesquisa\n\n## Copywriting\n", encoding="utf-8")

    refs = {"segment": "saas", "frankenstein": {}, "inspirational": [], "competitors": []}
    refs_path = tmp_path / "references.json"
    refs_path.write_text(json.dumps(refs), encoding="utf-8")

    monkeypatch.setattr(lib, "judge_artifact",
                        lambda *a, **kw: {"save": False, "reason": "skip", "tags": [],
                                          "ace_type": "atlas", "priority": "low", "summary": ""})

    lib.after_research("x", str(refs_path), "Atlas/Maps/x MOC.md", index=False)

    text = moc.read_text(encoding="utf-8")
    assert "## Pesquisa" in text
    assert str(refs_path) in text or "references" in text


def test_after_research_writes_note_when_judged_save(tmp_path, monkeypatch):
    import server.librarian as lib
    monkeypatch.setattr(lib, "VAULT_PATH", tmp_path)

    moc_dir = tmp_path / "Atlas" / "Maps"
    moc_dir.mkdir(parents=True)
    moc = moc_dir / "x MOC.md"
    moc.write_text("## Pesquisa\n", encoding="utf-8")

    refs = {"segment": "saas", "frankenstein": {"hero": {"from_ref": "ref_01"}},
            "inspirational": [{"ref_id": "ref_01", "url": "https://a.com", "title": "A"}],
            "competitors": []}
    refs_path = tmp_path / "references.json"
    refs_path.write_text(json.dumps(refs), encoding="utf-8")

    monkeypatch.setattr(lib, "judge_artifact",
                        lambda *a, **kw: {"save": True, "tags": ["saas"], "ace_type": "atlas",
                                          "priority": "high", "reason": "novo", "summary": "x"})

    lib.after_research("x", str(refs_path), "Atlas/Maps/x MOC.md", index=False)

    notes = list((tmp_path / "Atlas" / "Utilities" / "Researcher").glob("*-x-references.md"))
    assert len(notes) == 1
    body = notes[0].read_text(encoding="utf-8")
    assert "saas" in body
    assert "ref_01" in body
