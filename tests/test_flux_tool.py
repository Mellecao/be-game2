import os
import base64
from unittest.mock import patch, MagicMock


def test_flux_tool_saves_png(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_API_URL", "http://fake-forge")
    fake_png_b64 = base64.b64encode(b"\x89PNG\r\n\x1a\nFAKE").decode()
    fake_response = MagicMock()
    fake_response.json.return_value = {"images": [fake_png_b64]}
    fake_response.raise_for_status.return_value = None

    from server.flux_tool import FluxImageTool
    tool = FluxImageTool(output_dir=str(tmp_path))
    with patch("server.flux_tool.requests.post", return_value=fake_response):
        result = tool._run("a cat in space")

    assert result.endswith(".png")
    assert os.path.exists(result)
    assert os.path.getsize(result) > 0


def test_flux_tool_handles_api_error(tmp_path):
    import requests as r
    from server.flux_tool import FluxImageTool
    tool = FluxImageTool(api_url="http://127.0.0.1:1", output_dir=str(tmp_path))
    with patch(
        "server.flux_tool.requests.post",
        side_effect=r.ConnectionError("refused"),
    ):
        result = tool._run("anything")
    assert "Erro ao chamar API do Forge" in result


import json
from pathlib import Path


def test_generate_all_images_iterates_manifest(tmp_path, monkeypatch):
    from server import flux_tool

    manifest = {"images": [
        {"id": "hero", "prompt_pt": "hero text", "prompt_en": "hero",
         "purpose": "p", "width": 1024, "height": 1024, "convert_to_3d": False},
        {"id": "feat", "prompt_pt": "feat", "prompt_en": "feat eng",
         "purpose": "p", "width": 1024, "height": 1024, "convert_to_3d": False},
    ]}
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    out_path = tmp_path / "manifest_resolved.json"

    calls = []
    def fake_run(self, prompt):
        calls.append(prompt)
        png = tmp_path / f"{len(calls)}.png"
        png.write_bytes(b"\x89PNG")
        return str(png)

    monkeypatch.setattr(flux_tool.FluxImageTool, "_generate", fake_run)

    tool = flux_tool.GenerateAllImagesTool()
    result = tool._run(manifest_path=str(manifest_path), output_path=str(out_path))

    assert len(calls) == 2
    resolved = json.loads(out_path.read_text(encoding="utf-8"))
    assert resolved["images"][0]["png_path"].endswith(".png")
    assert "Geradas" in result or "2" in result
