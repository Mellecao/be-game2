import os
from unittest.mock import patch, MagicMock


def test_hunyuan_returns_glb_path(tmp_path, monkeypatch):
    img = tmp_path / "in.png"
    img.write_bytes(b"\x89PNG-fake")
    fake_glb = tmp_path / "out.glb"
    fake_glb.write_bytes(b"glb-bytes")

    fake_response = MagicMock()
    fake_response.json.return_value = {"path": str(fake_glb)}
    fake_response.raise_for_status.return_value = None

    from server.hunyuan3d_tool import Hunyuan3DTool
    tool = Hunyuan3DTool()
    with patch("server.hunyuan3d_tool.requests.post", return_value=fake_response):
        result = tool._run(image_path=str(img))
    assert result == str(fake_glb)


def test_hunyuan_handles_api_error(tmp_path):
    img = tmp_path / "in.png"
    img.write_bytes(b"x")
    import requests as r
    from server.hunyuan3d_tool import Hunyuan3DTool
    tool = Hunyuan3DTool(api_url="http://127.0.0.1:1")
    with patch(
        "server.hunyuan3d_tool.requests.post",
        side_effect=r.ConnectionError("refused"),
    ):
        result = tool._run(image_path=str(img))
    assert "Erro ao chamar API do Hunyuan" in result


def test_hunyuan_validates_image_exists(tmp_path):
    from server.hunyuan3d_tool import Hunyuan3DTool
    tool = Hunyuan3DTool()
    result = tool._run(image_path=str(tmp_path / "no-such-file.png"))
    assert "Erro" in result and "nao existe" in result.lower()


import json
from pathlib import Path


def test_generate_all_glbs_iterates_only_convert_to_3d(tmp_path, monkeypatch):
    from server import hunyuan3d_tool

    resolved = {"images": [
        {"id": "hero", "png_path": str(tmp_path / "hero.png"), "convert_to_3d": False},
        {"id": "obj1", "png_path": str(tmp_path / "obj1.png"), "convert_to_3d": True},
        {"id": "obj2", "png_path": str(tmp_path / "obj2.png"), "convert_to_3d": True},
    ]}
    for it in resolved["images"]:
        Path(it["png_path"]).write_bytes(b"\x89PNG")

    resolved_path = tmp_path / "manifest_resolved.json"
    resolved_path.write_text(json.dumps(resolved), encoding="utf-8")

    calls = []
    def fake_run(self, image_path):
        calls.append(image_path)
        glb = tmp_path / (Path(image_path).stem + ".glb")
        glb.write_bytes(b"glTF")
        return str(glb)

    monkeypatch.setattr(hunyuan3d_tool.Hunyuan3DTool, "_run", fake_run)

    tool = hunyuan3d_tool.GenerateAllGlbsTool()
    result = tool._run(manifest_resolved_path=str(resolved_path))

    assert len(calls) == 2  # so os com convert_to_3d=True
    out = json.loads(resolved_path.read_text(encoding="utf-8"))
    assert out["images"][1]["glb_path"].endswith(".glb")
    assert "glb_path" not in out["images"][0]
