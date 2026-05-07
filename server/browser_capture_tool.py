"""Captura screenshots full-page + por secao via Playwright."""
from __future__ import annotations

from pathlib import Path
from typing import Dict
from crewai.tools import BaseTool
from pydantic import Field

from .playwright_helper import acquire_browser, respect_rate_limit


class BrowserCaptureTool(BaseTool):
    name: str = "browser_capture"
    description: str = (
        "Captura screenshots de uma URL: full-page, hero (above-the-fold), "
        "e secoes ao longo do scroll. Retorna dict com paths."
    )
    output_dir: str = Field(default="output/research")
    viewport_width: int = Field(default=1920)
    viewport_height: int = Field(default=1080)

    def _run(self, url: str, ref_id: str) -> Dict[str, str]:
        respect_rate_limit()
        ctx = acquire_browser()
        out_dir = Path(self.output_dir) / ref_id
        out_dir.mkdir(parents=True, exist_ok=True)

        page = ctx.new_page()
        try:
            page.set_viewport_size({"width": self.viewport_width, "height": self.viewport_height})
            page.goto(url, wait_until="networkidle", timeout=45000)

            paths: Dict[str, str] = {}

            full_path = out_dir / "full.png"
            page.screenshot(path=str(full_path), full_page=True)
            paths["full"] = str(full_path.resolve())

            hero_path = out_dir / "hero.png"
            page.screenshot(path=str(hero_path), full_page=False)
            paths["hero"] = str(hero_path.resolve())

            total_height = page.evaluate("document.body.scrollHeight")
            step = int(self.viewport_height * 0.8)
            section_idx = 1
            scroll_y = step
            while scroll_y < total_height and section_idx <= 6:
                page.evaluate(f"window.scrollTo(0, {scroll_y})")
                page.wait_for_timeout(300)
                sec_path = out_dir / f"section_{section_idx}.png"
                page.screenshot(path=str(sec_path), full_page=False)
                paths[f"section_{section_idx}"] = str(sec_path.resolve())
                section_idx += 1
                scroll_y += step

            return paths
        finally:
            page.close()
