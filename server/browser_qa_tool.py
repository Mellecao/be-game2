"""Browser automation pro QA visual."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List
from crewai.tools import BaseTool
from pydantic import Field

from .playwright_helper import acquire_browser, respect_rate_limit


VIEWPORTS = {
    "desktop_1920": (1920, 1080),
    "desktop_1440": (1440, 900),
    "tablet_768":   (768, 1024),
    "mobile_375":   (375, 812),
}


class BrowserQATool(BaseTool):
    name: str = "browser_qa"
    description: str = (
        "Captura screenshots do site renderizado. Metodos: screenshot_full, "
        "screenshot_sections, screenshot_responsive, inspect_element."
    )
    output_dir: str = Field(default="output/qa_visual/current")

    def screenshot_full(self, url: str) -> str:
        respect_rate_limit()
        ctx = acquire_browser()
        out_dir = Path(self.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        page = ctx.new_page()
        try:
            page.goto(url, wait_until="networkidle", timeout=45000)
            path = out_dir / "full.png"
            page.screenshot(path=str(path), full_page=True)
            return str(path.resolve())
        finally:
            page.close()

    def screenshot_sections(self, url: str, max_count: int = 6) -> List[str]:
        respect_rate_limit()
        ctx = acquire_browser()
        out_dir = Path(self.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        paths: List[str] = []
        page = ctx.new_page()
        try:
            page.set_viewport_size({"width": 1920, "height": 1080})
            page.goto(url, wait_until="networkidle", timeout=45000)

            hero = out_dir / "hero.png"
            page.screenshot(path=str(hero), full_page=False)
            paths.append(str(hero.resolve()))

            total = page.evaluate("document.body.scrollHeight")
            step = int(1080 * 0.8)
            idx = 1
            y = step
            while y < total and idx <= max_count:
                page.evaluate(f"window.scrollTo(0, {y})")
                page.wait_for_timeout(300)
                p = out_dir / f"section_{idx}.png"
                page.screenshot(path=str(p), full_page=False)
                paths.append(str(p.resolve()))
                idx += 1
                y += step
            return paths
        finally:
            page.close()

    def screenshot_responsive(self, url: str) -> Dict[str, str]:
        respect_rate_limit()
        ctx = acquire_browser()
        out_dir = Path(self.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        out: Dict[str, str] = {}
        for name, (w, h) in VIEWPORTS.items():
            page = ctx.new_page()
            try:
                page.set_viewport_size({"width": w, "height": h})
                page.goto(url, wait_until="networkidle", timeout=45000)
                p = out_dir / f"{name}.png"
                page.screenshot(path=str(p), full_page=False)
                out[name] = str(p.resolve())
            finally:
                page.close()
        return out

    def inspect_element(self, url: str, selector: str) -> str:
        respect_rate_limit()
        ctx = acquire_browser()
        out_dir = Path(self.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        page = ctx.new_page()
        try:
            page.goto(url, wait_until="networkidle", timeout=45000)
            el = page.locator(selector).first
            safe = selector.replace(":", "_").replace(">", "_").replace(" ", "_")
            p = out_dir / f"el_{safe}.png"
            el.screenshot(path=str(p))
            return str(p.resolve())
        finally:
            page.close()

    def _run(self, url: str, mode: str = "responsive") -> Dict:
        if mode == "full":
            return {"full": self.screenshot_full(url)}
        if mode == "sections":
            return {"sections": self.screenshot_sections(url)}
        return self.screenshot_responsive(url)
