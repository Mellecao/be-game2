import http.server
import socketserver
import threading
import time
from pathlib import Path

import pytest


@pytest.fixture
def local_server(tmp_path):
    html = """<!doctype html><html><body style='margin:0'>
    <div style='height:1080px;background:#f00'>HERO</div>
    <div style='height:1080px;background:#0f0'>S2</div>
    </body></html>"""
    (tmp_path / "index.html").write_text(html, encoding="utf-8")
    handler = lambda *a, **kw: http.server.SimpleHTTPRequestHandler(*a, directory=str(tmp_path), **kw)
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    time.sleep(0.2)
    yield f"http://127.0.0.1:{port}"
    httpd.shutdown()


def test_screenshot_responsive_creates_4_viewports(local_server, tmp_path):
    from server.browser_qa_tool import BrowserQATool

    tool = BrowserQATool(output_dir=str(tmp_path))
    paths = tool.screenshot_responsive(url=local_server)

    for vp in ("desktop_1920", "desktop_1440", "tablet_768", "mobile_375"):
        assert vp in paths
        assert (tmp_path / f"{vp}.png").exists()


def test_screenshot_sections_creates_multiple_pngs(local_server, tmp_path):
    from server.browser_qa_tool import BrowserQATool

    tool = BrowserQATool(output_dir=str(tmp_path))
    paths = tool.screenshot_sections(url=local_server)

    assert len(paths) >= 1
    assert any(Path(p).exists() for p in paths)
