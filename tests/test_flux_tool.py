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
