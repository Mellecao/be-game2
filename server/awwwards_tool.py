"""Scraper de awwwards/dribbble/behance. Retorna lista de refs com url+title."""
from __future__ import annotations

from typing import List, Dict
from crewai.tools import BaseTool
from pydantic import Field
from bs4 import BeautifulSoup

from .playwright_helper import acquire_browser, respect_rate_limit


def _fetch_html(url: str) -> str:
    """Busca HTML via Playwright (passa anti-bot do awwwards)."""
    respect_rate_limit()
    ctx = acquire_browser()
    page = ctx.new_page()
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        return page.content()
    finally:
        page.close()


def _absolutize(href: str) -> str:
    if href.startswith("//"):
        return "https:" + href
    if href.startswith("/"):
        return "https://www.awwwards.com" + href
    return href


def parse_awwwards_html(html: str, max_count: int = 5) -> List[Dict[str, str]]:
    """Extrai refs da listagem de categorias do awwwards.

    Awwwards renderiza cada submission como `<li class="js-collectable">`
    contendo um `<figure class="figure-rollover">` com o link
    `a.figure-rollover__link` (href interno `/sites/<slug>`).
    """
    soup = BeautifulSoup(html, "html.parser")
    out: List[Dict[str, str]] = []
    seen_urls: set[str] = set()

    cards = soup.select("li.js-collectable")
    if not cards:
        cards = soup.select("figure.figure-rollover")

    for card in cards:
        link = card.select_one("a.figure-rollover__link")
        if not link:
            link = card.select_one("a[href^='/sites/']")
        if not link:
            continue

        href = link.get("href", "").strip()
        if not href:
            continue
        url = _absolutize(href)
        if not url.startswith("https://"):
            continue
        if url in seen_urls:
            continue

        title = (link.get("aria-label") or "").strip()
        if not title:
            title_row = card.select_one(".figure-rollover__row:nth-of-type(2)")
            if title_row:
                title = title_row.get_text(strip=True)
        if not title:
            img = link.select_one("img[alt]")
            if img:
                title = img.get("alt", "").strip()
        if not title:
            title = url

        out.append({
            "source": "awwwards",
            "url": url,
            "title": title,
        })
        seen_urls.add(url)

        if len(out) >= max_count:
            break

    if not out:
        # Fallback genérico: qualquer link interno que aponte para /sites/<slug>.
        for a in soup.select("a[href^='/sites/']"):
            href = a.get("href", "").strip()
            url = _absolutize(href)
            if not url.startswith("https://") or url in seen_urls:
                continue
            title = (a.get("aria-label") or a.get_text(strip=True) or url).strip()
            out.append({"source": "awwwards", "url": url, "title": title})
            seen_urls.add(url)
            if len(out) >= max_count:
                break

    return out[:max_count]


class AwwwardsTool(BaseTool):
    name: str = "awwwards_search"
    description: str = (
        "Busca refs no awwwards filtrando por segmento (saas, e-commerce, "
        "agency, fintech). Retorna lista de {source, url, title}."
    )
    max_count: int = Field(default=5)

    def _run(self, segment: str, max_count: int = 5) -> List[Dict[str, str]]:
        slug = segment.lower().replace(" ", "-")
        url = f"https://www.awwwards.com/websites/{slug}/"
        html = _fetch_html(url)
        return parse_awwwards_html(html, max_count=max_count)
