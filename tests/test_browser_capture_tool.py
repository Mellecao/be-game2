import http.server
import socketserver
import threading
import time
from pathlib import Path

import pytest


@pytest.fixture
def local_server(tmp_path):
    """Sobe http.server local com pagina HTML scrollable."""
    html = """<!doctype html><html><head><style>
    body{margin:0} .sec{height:1080px;display:flex;align-items:center;justify-content:center;font-size:64px}
    #s1{background:#f00} #s2{background:#0f0} #s3{background:#00f}
    </style></head><body>
    <div class='sec' id='s1'>HERO</div>
    <div class='sec' id='s2'>SECTION 2</div>
    <div class='sec' id='s3'>FOOTER</div>
    </body></html>"""
    (tmp_path / "index.html").write_text(html, encoding="utf-8")

    handler = lambda *a, **kw: http.server.SimpleHTTPRequestHandler(*a, directory=str(tmp_path), **kw)
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    time.sleep(0.2)
    yield f"http://127.0.0.1:{port}"
    httpd.shutdown()


def test_capture_full_and_sections_creates_pngs(local_server, tmp_path):
    from server.browser_capture_tool import BrowserCaptureTool

    tool = BrowserCaptureTool(output_dir=str(tmp_path))
    paths = tool._run(url=local_server, ref_id="ref_test")

    out = tmp_path / "ref_test"
    assert (out / "full.png").exists()
    assert (out / "hero.png").exists()
    assert any(p.name.startswith("section_") for p in out.glob("*.png"))
    assert paths["full"].endswith("full.png")
    assert paths["hero"].endswith("hero.png")
