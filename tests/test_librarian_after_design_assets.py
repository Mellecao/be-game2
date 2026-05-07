import json


def test_after_design_writes_manifest_json(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    (vault / "Atlas" / "Maps").mkdir(parents=True)
    moc = vault / "Atlas" / "Maps" / "myslug MOC.md"
    moc.write_text("# myslug MOC\n\n## Design\n\n## Imagens\n\n## Modelos 3D\n", encoding="utf-8")

    import server.librarian as lib
    monkeypatch.setattr(lib, "VAULT_PATH", vault)

    manifest = {"images": [{"id": "hero", "purpose": "bg"}]}
    lib.after_design(
        slug="myslug",
        guide_path="Atlas/Utilities/Designer/2026-01-01-myslug-visual-guide.md",
        manifest_str=json.dumps(manifest),
        moc_path="Atlas/Maps/myslug MOC.md",
        index=False,
    )

    manifest_md = list((vault / "Atlas" / "Utilities" / "Designer").glob("*-myslug-manifest.json"))
    assert manifest_md, "manifest json nao foi criado"


def test_after_assets_writes_md_lists(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    (vault / "Atlas" / "Maps").mkdir(parents=True)
    moc = vault / "Atlas" / "Maps" / "abc MOC.md"
    moc.write_text("# abc MOC\n\n## Design\n\n## Imagens\n\n## Modelos 3D\n", encoding="utf-8")

    import server.librarian as lib
    monkeypatch.setattr(lib, "VAULT_PATH", vault)

    resolved = {"images": [
        {"id": "hero", "png_path": "/abs/hero.png", "prompt_en": "...", "purpose": "bg"},
        {"id": "logo", "png_path": "/abs/logo.png", "glb_path": "/abs/logo.glb", "prompt_en": "...", "purpose": "logo"},
    ]}
    lib.after_assets(
        slug="abc",
        resolved_manifest=resolved,
        project_dir=str(tmp_path / "fakeproj"),
        moc_path="Atlas/Maps/abc MOC.md",
        index=False,
    )

    assets_md = list((vault / "Atlas" / "Utilities" / "ImageArtist").glob("*-abc-assets.md"))
    models_md = list((vault / "Atlas" / "Utilities" / "3DArtist").glob("*-abc-models.md"))
    assert assets_md and models_md
