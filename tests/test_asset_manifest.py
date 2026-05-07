import json


def test_parse_valid_manifest():
    from server.asset_manifest import parse_manifest
    text = """# Guia
... blá blá ...

```asset_manifest
{
  "images": [
    {"id": "hero", "prompt_pt": "fundo escuro", "purpose": "hero", "convert_to_3d": false}
  ]
}
```
"""
    out = parse_manifest(text)
    assert "images" in out
    assert out["images"][0]["id"] == "hero"


def test_parse_missing_fence():
    from server.asset_manifest import parse_manifest
    out = parse_manifest("# guia sem manifest\n\nbla bla")
    assert out == {"images": []}


def test_parse_invalid_json():
    from server.asset_manifest import parse_manifest
    text = "```asset_manifest\nNOT JSON\n```"
    out = parse_manifest(text)
    assert out == {"images": []}


def test_parse_extracts_only_first_fence():
    from server.asset_manifest import parse_manifest
    text = """```asset_manifest
{"images": [{"id": "a"}]}
```

```asset_manifest
{"images": [{"id": "b"}]}
```
"""
    out = parse_manifest(text)
    assert out["images"][0]["id"] == "a"


def test_write_resolved_creates_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from server.asset_manifest import write_resolved, read_resolved
    manifest = {"images": [{"id": "hero", "png_path": "/abs/hero.png"}]}
    path = write_resolved("my-slug", manifest)
    assert path.exists()
    out = read_resolved("my-slug")
    assert out["images"][0]["id"] == "hero"
