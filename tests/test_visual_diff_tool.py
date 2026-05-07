def test_visual_diff_compares_pair_returns_verdict(monkeypatch, tmp_path):
    cur = tmp_path / "current_hero.png"
    ref = tmp_path / "ref_hero.png"
    cur.write_bytes(b"\x89PNG")
    ref.write_bytes(b"\x89PNG")

    from server import visual_diff_tool

    fake = (
        '{"section": "hero", "verdict": "REPROVADO", '
        '"issues": ["Padding 40px abaixo da ref (deveria 96px)", "CTA sem contraste"], '
        '"reference_used": "ref_hero.png", "current_screenshot": "current_hero.png"}'
    )
    monkeypatch.setattr(visual_diff_tool, "_call_vision_diff",
                        lambda current, reference, section: fake)

    tool = visual_diff_tool.VisualDiffTool()
    out = tool._run(current_path=str(cur), reference_path=str(ref), section="hero")
    assert out["verdict"] == "REPROVADO"
    assert len(out["issues"]) == 2


def test_visual_diff_handles_malformed_json(monkeypatch, tmp_path):
    cur = tmp_path / "c.png"; ref = tmp_path / "r.png"
    cur.write_bytes(b"\x89PNG"); ref.write_bytes(b"\x89PNG")

    from server import visual_diff_tool
    monkeypatch.setattr(visual_diff_tool, "_call_vision_diff",
                        lambda *a, **kw: "garbage not json")

    tool = visual_diff_tool.VisualDiffTool()
    out = tool._run(current_path=str(cur), reference_path=str(ref), section="x")
    assert out["verdict"] == "ERRO"
    assert "parse_error" in out
