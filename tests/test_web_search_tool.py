def test_web_search_returns_list_of_dicts(monkeypatch):
    from server import web_search_tool

    fake_results = [
        {"href": "https://a.com", "title": "A", "body": "snippet a"},
        {"href": "https://b.com", "title": "B", "body": "snippet b"},
    ]

    class FakeDDGS:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def text(self, query, max_results=10):
            assert max_results <= 10
            return fake_results

    monkeypatch.setattr(web_search_tool, "DDGS", FakeDDGS)

    tool = web_search_tool.WebSearchTool()
    out = tool._run("plataforma cursos online Brasil")
    assert len(out) == 2
    assert out[0]["url"] == "https://a.com"
    assert out[0]["title"] == "A"


def test_web_search_handles_empty_results(monkeypatch):
    from server import web_search_tool

    class FakeDDGS:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def text(self, query, max_results=10): return []

    monkeypatch.setattr(web_search_tool, "DDGS", FakeDDGS)
    tool = web_search_tool.WebSearchTool()
    assert tool._run("xyz nonexistent") == []
