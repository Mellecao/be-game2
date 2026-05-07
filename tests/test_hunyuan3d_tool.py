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
