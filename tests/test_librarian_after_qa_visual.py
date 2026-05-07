import json


def test_after_qa_visual_writes_moc_link_always(tmp_path, monkeypatch):
    import server.librarian as lib
    monkeypatch.setattr(lib, "VAULT_PATH", tmp_path)

    moc_dir = tmp_path / "Atlas" / "Maps"
    moc_dir.mkdir(parents=True)
    moc = moc_dir / "x MOC.md"
    moc.write_text("## QA Visual\n\n## Deploy\n", encoding="utf-8")

    report = [{"section": "hero", "verdict": "APROVADO", "issues": []}]
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")

    monkeypatch.setattr(lib, "judge_artifact",
                        lambda *a, **kw: {"save": False, "reason": "ok review", "tags": [],
                                          "ace_type": "atlas", "priority": "low", "summary": ""})

    lib.after_qa_visual("x", str(report_path), str(tmp_path), "Atlas/Maps/x MOC.md", index=False)

    assert "## QA Visual" in moc.read_text(encoding="utf-8")


def test_after_qa_visual_writes_note_when_save(tmp_path, monkeypatch):
    import server.librarian as lib
    monkeypatch.setattr(lib, "VAULT_PATH", tmp_path)

    moc_dir = tmp_path / "Atlas" / "Maps"
    moc_dir.mkdir(parents=True)
    moc = moc_dir / "x MOC.md"
    moc.write_text("## QA Visual\n", encoding="utf-8")

    report = [{"section": "hero", "verdict": "REPROVADO",
               "issues": ["padding 40px deveria ser 96px"]}]
    rp = tmp_path / "report.json"
    rp.write_text(json.dumps(report), encoding="utf-8")

    monkeypatch.setattr(lib, "judge_artifact",
                        lambda *a, **kw: {"save": True, "tags": ["qa"], "ace_type": "atlas",
                                          "priority": "high", "reason": "issue novo",
                                          "summary": "padding hero 96px standard"})

    lib.after_qa_visual("x", str(rp), str(tmp_path), "Atlas/Maps/x MOC.md", index=False)

    notes = list((tmp_path / "Atlas" / "Utilities" / "QA-Visual").glob("*-x-review.md"))
    assert len(notes) == 1
    body = notes[0].read_text(encoding="utf-8")
    assert "REPROVADO" in body
    assert "padding 40px" in body
