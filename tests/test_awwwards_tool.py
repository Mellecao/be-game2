from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "awwwards_saas.html"


def test_parse_awwwards_returns_list_of_refs():
    from server.awwwards_tool import parse_awwwards_html
    html = FIXTURE.read_text(encoding="utf-8")
    refs = parse_awwwards_html(html, max_count=5)
    assert isinstance(refs, list)
    assert len(refs) >= 1
    for r in refs:
        assert "url" in r
        assert "title" in r
        assert r["source"] == "awwwards"
        assert r["url"].startswith("https://")


def test_awwwards_tool_filters_by_segment(monkeypatch):
    from server import awwwards_tool

    captured = {}
    def fake_fetch(url):
        captured["url"] = url
        return FIXTURE.read_text(encoding="utf-8")

    monkeypatch.setattr(awwwards_tool, "_fetch_html", fake_fetch)
    tool = awwwards_tool.AwwwardsTool()
    out = tool._run(segment="saas", max_count=3)
    assert "saas" in captured["url"].lower()
    assert len(out) <= 3
