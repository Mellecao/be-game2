# tests/test_librarian.py
import pytest
from pathlib import Path


def test_enforce_asset_name_valid():
    from server.librarian import enforce_asset_name
    assert enforce_asset_name("2026-05-05-rose-beauty-copy.md", r"^\d{4}-\d{2}-\d{2}-[\w-]+-copy\.md$") is True


def test_enforce_asset_name_invalid():
    from server.librarian import enforce_asset_name
    assert enforce_asset_name("layout_final_2.png", r"^\d{4}-\d{2}-\d{2}-[\w-]+-copy\.md$") is False


def test_after_copy_appends_wikilink_to_moc(tmp_path, monkeypatch):
    import server.librarian as lib
    import server.vault_writer as vw
    monkeypatch.setattr(vw, "VAULT_PATH", tmp_path)
    monkeypatch.setattr(lib, "VAULT_PATH", tmp_path)

    moc_dir = tmp_path / "Atlas" / "Maps"
    moc_dir.mkdir(parents=True)
    moc_file = moc_dir / "rose-beauty MOC.md"
    moc_file.write_text(
        "---\nagent: planner\n---\n\n# rose-beauty MOC\n\n## Copywriting\n\n## Design\n",
        encoding="utf-8",
    )

    copy_path = "Atlas/Notes/Sources/Copywriter/2026-05-05-rose-beauty-copy.md"
    (tmp_path / "Atlas/Notes/Sources/Copywriter").mkdir(parents=True)
    (tmp_path / copy_path).write_text("# Copy\nConteudo.", encoding="utf-8")

    lib.after_copy("rose-beauty", copy_path, "Atlas/Maps/rose-beauty MOC.md", index=False)

    updated = moc_file.read_text(encoding="utf-8")
    assert "[[Atlas/Notes/Sources/Copywriter/2026-05-05-rose-beauty-copy]]" in updated


def test_after_deploy_moves_effort_to_archives(tmp_path, monkeypatch):
    import server.librarian as lib
    monkeypatch.setattr(lib, "VAULT_PATH", tmp_path)

    (tmp_path / "Efforts" / "On").mkdir(parents=True)
    effort = tmp_path / "Efforts" / "On" / "rose-beauty (E).md"
    effort.write_text("# rose-beauty\nOn.", encoding="utf-8")

    (tmp_path / "Atlas" / "Maps").mkdir(parents=True)
    moc = tmp_path / "Atlas" / "Maps" / "rose-beauty MOC.md"
    moc.write_text("## Deploy\n\n", encoding="utf-8")

    lib.after_deploy(
        slug="rose-beauty",
        github_url="https://github.com/v27me/rose-beauty",
        moc_path="Atlas/Maps/rose-beauty MOC.md",
        effort_path="Efforts/On/rose-beauty (E).md",
        index=False,
    )

    assert not effort.exists()
    assert (tmp_path / "Efforts" / "Archives" / "rose-beauty (E).md").exists()

    moc_text = moc.read_text(encoding="utf-8")
    assert "https://github.com/v27me/rose-beauty" in moc_text
