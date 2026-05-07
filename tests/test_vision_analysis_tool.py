from pathlib import Path


def test_vision_analysis_parses_json(monkeypatch, tmp_path):
    img = tmp_path / "fake.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")

    from server import vision_analysis_tool

    fake_response = (
        '{"tipografia": "bold serif 64px", '
        '"cores": ["#fff", "#000"], '
        '"layout": "hero centralizado", '
        '"cta": "primario azul", '
        '"padroes": ["minimalista"]}'
    )

    monkeypatch.setattr(
        vision_analysis_tool,
        "_call_vision",
        lambda image_path, context: fake_response,
    )

    tool = vision_analysis_tool.VisionAnalysisTool()
    out = tool._run(image_path=str(img), context="hero saas")

    assert out["tipografia"] == "bold serif 64px"
    assert out["cores"] == ["#fff", "#000"]


def test_vision_analysis_handles_malformed_json(monkeypatch, tmp_path):
    img = tmp_path / "fake.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")
    from server import vision_analysis_tool

    monkeypatch.setattr(vision_analysis_tool, "_call_vision",
                        lambda image_path, context: "not json at all")

    tool = vision_analysis_tool.VisionAnalysisTool()
    out = tool._run(image_path=str(img), context="x")

    assert out == {"raw": "not json at all", "parse_error": True}
